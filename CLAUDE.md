# CLAUDE.md — wndrverse

Open-source community networking tool. Passive agent network for communities.

## What this is

Two-layer Telegram system:
- **Bus** (Topic 1): agents write activity, people read silently
- **Showcase** (Topic 2): curator picks 1 match/post per day

## Repositories & deployment map

Three related repos — easy to confuse:

| Repo | What it is | Where |
|------|-----------|-------|
| `renatmannanov/wndrverse` | this repo (was `re_verse`, renamed 2026-05) — main: plans, curator, docs, **core/bot/digest pipeline** | local `~/projects/wndrverse`; **deployed VPS `~/wndrverse`** (ingest bot + embedder timer + DB, see Production section) |
| `renatmannanov/wndrverse_agent_claude` | Claude agent, extracted to standalone (commit 7f61088) — the curator/agent piece | VPS `~/wndrverse_agent_claude` (migrating to `~/claude-hub/projects/wndrverse`) |
| `renatmannanov/claude_hub` | shared hub scaffold for all Claude SDK agents | VPS `~/claude-hub` |

**VPS:** `rm_agent@62.238.31.95` (Hetzner CX33, hostname `openclaw-prod`, Ubuntu 24.04). Same server as OpenClaw/Hermes but fully isolated.
SSH: `ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95`
**Do NOT touch on VPS:** `~/.openclaw/`, `~/.hermes/`, `~/.codex/`, `~/.claude/` — not ours.

## Commands

```bash
# Install deps
pip install python-telegram-bot httpx anthropic

# Run curator locally
python curator/main.py

# Run your agent (Option A)
python agent-template/agent_cron.py

# Create managed agent (Option B, run once)
python agent-template/agent_managed.py create
```

### Community brain (core/) — digest pipeline

```bash
docker compose up -d db                              # postgres+pgvector on 5434
python -m core.db init                               # create schema
python -m core.ingest.loaders --dir <exports>        # load messages (or env WNDR_EXPORTS_DIR)
python -m core.enrich.embedder --estimate            # cost estimate (no API spend)
python -m core.enrich.embedder                        # real embeddings (spends OpenAI)
python -m delivery digest --topic offerings --period all   # digest → stdout (1w/1m/all)
```

Needs `.env` (DATABASE_URL, OPENAI_API_KEY, WNDR_EXPORTS_DIR — see `.env.example`).
PII: only text + anonymous `[@N]` author keys go to OpenAI; names/@handles are
substituted locally on output (see Digest author grouping below).
`data/` is gitignored — community messages are never committed.

**Dedup key:** `external_id = tg_{chat_id}_{msg_id}` — unified across the file
backfill and the realtime bot so the same message dedups to one row (per-row
SELECT, not ON CONFLICT — keys must match byte-for-byte). chat_id is the
`-100…` form. Legacy exports without a `chat_id` field fall back to the old
`wndr_{chat_name}_{msg_id}` key. Telethon exports come from `telegram-gather`
(`fetch_topic.py` writes `chat_id`; separate repo). DB backups (`*.sql`) are
gitignored — they hold PII.

### Realtime ingest bot (bot/) — live group → fragments

```bash
python -m bot.ingest_bot                             # polling listener (long-lived); module form only
```

Writes new group messages into `fragments` in realtime via the same `ingest()`
funnel as the file loader. Needs `BOT_TOKEN_INGEST` (separate bot, privacy mode
OFF) and a `core/ingest/topic_map.json` mapping `(chat_id, thread_id) → topic`
(gitignored — holds real chat_ids; copy from `topic_map.example.json`).
Unknown chats are skipped + logged. Run on Windows with `PYTHONUTF8=1` if the
console mangles Cyrillic.

The same bot also serves `/summary <topic> <YYYY-MM-DD> <YYYY-MM-DD>` — an
on-demand digest over an EXACT (inclusive) date range, DM'd to the caller. Access
is whitelisted by `WNDR_SUMMARY_ALLOWED` (CSV of user_ids; empty => nobody,
fail-closed). `/summary` with no args replies with the format + the list of
topics that actually have fragments. Unknown topic / bad date / from>till → a
friendly reply with no OpenAI spend; 0 fragments for the range → "нет сообщений"
(also no spend). Reuses `delivery.cli.build_digest` (the shared synth+humanize
core), so PII stays local (`[@N]` → `Name @handle` from the DB; see Digest author
grouping below). The caller must `/start` the bot in DM first, else the result
reply hints `/start`.

Two messages: (1) an immediate ack ("Топик … | Период … | Найдено N, передаю в
модель максимум 150. Собираю саммари…") via a cheap `count_fragments` DB query
BEFORE any OpenAI spend; (2) the digest itself as its own DM, kept clean (no
stats line) so it can later be forwarded to a dedicated topic verbatim. Both go
to the caller's DM, never the group.

Synthesis (`core/brain/synthesis.py`): for ≤ `MAX_FRAGMENTS_WITHOUT_SELECTION`
(=150) fragments the whole period is fed to the model in one pass; above that a
Pass-1 LLM selection trims to ~20 (now over FULL text, not 100-char previews).
The 150 threshold + full-text selection came from a 2026-06-04 A/B/C test:
synthesizing all messages of a monthly range beat selection (more themes, cheaper).

**Digest author grouping + `[@N]` contract** (2026-06-05): the digest references
PEOPLE, not messages. Before Pass-2, `_group_by_author` (synthesis.py) groups the
fragments by author (key: `sender_id` → `author_name` → anon) into one `[@N]` block
per author — so a multi-message author becomes a single line in «КТО ЧТО», not one
line per message. Only `[@N]` + texts go to OpenAI (no names). `synthesize` returns
`author_refs {N: "Name @handle"}`; `delivery.cli.humanize_author_refs` substitutes
`[@N]` → that display string locally, WITHOUT brackets so the `@handle` (Telegram
username from `metadata->>'username'`, already captured at ingest) auto-links to the
profile. `build_digest` also prepends a deterministic `📅 topic · from — till`
header (dates from the request, not the LLM) into `result['text']` so it survives a
verbatim forward. Synthesis temperature is 0.4 (livelier; names pinned by `[@N]`,
can't desync); Pass-1 selection stays 0.0. Prompt `core/prompts/digest_synthesis.md`
caps «КТО ЧТО» at ~15 participants and targets ~2800 chars to stay under Telegram's
4096 cap after name substitution. The old `[#id]`-per-message contract is gone from
the synthesis path (legacy `humanize_refs` is unused by the digest).

### Digest scheduler (digest/) — daily digest → user's DM

```bash
python -m digest.scheduler                           # sleep-loop: once a day at WNDR_DIGEST_AT
python -m digest.scheduler --now                     # run once immediately and exit (manual / smoke)
```

Long-lived stdlib sleep-loop (no APScheduler/cron). Once a day at `WNDR_DIGEST_AT`
in zone `WNDR_DIGEST_TZ` it synthesizes a digest per `WNDR_DIGEST_TOPICS` and DMs
it to `WNDR_DIGEST_DM_USER_ID` via the ingest bot, reusing `delivery.cli._run_digest`
(synth → humanize `[@N]` author refs locally → send). Topic with 0 fragments for the period is
skipped (no OpenAI spend). User must `/start` the ingest bot first (Telegram won't
let a bot message first). Schedule pinned to a named zone so a UTC VPS move won't
shift the send moment. No missed-run recovery in MVP.

### Production (systemd on VPS)

Deployed 2026-06-04 to the VPS (`rm_agent@62.238.31.95`, see deploy map). The
core/bot/digest pipeline lives in **`~/wndrverse`** (its own dir in home — NOT
inside `~/claude-hub`, which is a separate git scaffold for Claude SDK agents).
Docker (postgres+pgvector on :5434) + a Python venv (`~/wndrverse/.venv`).

The corpus was moved by a **full `pg_dump`** of the local DB (DDL + `CREATE
EXTENSION vector` + data) restored into a fresh empty DB — NO `core.db init`
before restore (the full dump carries the schema; running init first would cause
`relation already exists`). The `.sql` dump (holds PII) is deleted after restore,
local and on the VPS. `.env` (chmod 600) and `topic_map.json` are gitignored,
created by hand on the VPS.

systemd units (all `~/wndrverse`-pathed, `User=rm_agent`):
- `wndr-ingest-bot.service` — long-lived realtime listener (`-m bot.ingest_bot`).
- `wndr-embedder.timer` → `.service` — `-m core.enrich.embedder` every 6h, batch
  over `embedding IS NULL` (cheap delta; corpus from dump already embedded).
- `wndr-digest.timer` — daily DM digest. **NOT enabled yet** — see
  `task_tracker/backlog/enable-daily-digest-timer.md` (deferred by user).

Ops commands:
```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse
sudo systemctl status wndr-ingest-bot            # active (running)
systemctl list-timers | grep wndr                # embedder next-run
journalctl -u wndr-ingest-bot -f                 # live ingest log
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*), count(*)-count(DISTINCT external_id) dup FROM fragments;"
```
Deploy update: `git pull origin master` in `~/wndrverse`, then
`sudo systemctl restart wndr-ingest-bot`. Do NOT touch OpenClaw/Hermes units.

## Key files

- `members.json` — list of participants and their sources
- `bus-protocol.md` — message format for the Bus
- `task_tracker/todo/PLAN.md` — current development plan
- `task_tracker/todo/ARCHITECTURE.md` — full architecture decisions
- `core/` — community brain (digest pipeline): db / ingest / store / enrich / brain / llm / prompts
- `delivery/` — digest CLI + output channels (stdout now; telegram = future)
- `bot/` — realtime ingest bot (polling listener → core ingest)
- `digest/` — daily digest scheduler (sleep-loop → core synth → user's DM)
- `docker-compose.yml` — postgres+pgvector (db `wndrverse`, port 5434)

## Env vars

```
BOT_TOKEN          — Telegram bot token (@BotFather)
BUS_CHAT_ID        — Telegram supergroup ID (Bus topic)
MY_USERNAME        — your Telegram username
TG_CHANNEL         — your public TG channel username
GITHUB_USERNAME    — your GitHub username
ANTHROPIC_API_KEY  — for Option B (Claude Managed Agent)
BOT_TOKEN_INGEST   — realtime ingest bot token (separate from BOT_TOKEN; privacy mode OFF)
WNDR_TOPIC_MAP     — path to topic_map.json (default core/ingest/topic_map.json)
WNDR_DIGEST_DM_USER_ID — Telegram user_id to DM the digest to (must /start the bot)
WNDR_DIGEST_TZ     — digest schedule timezone (default Asia/Almaty)
WNDR_DIGEST_AT     — digest run time HH:MM (default 09:00)
WNDR_DIGEST_PERIOD — message lookback window (default 1d)
WNDR_DIGEST_TOPICS — comma-separated topics (default questions_to_women,questions_to_men)
WNDR_SUMMARY_ALLOWED — CSV of Telegram user_ids allowed to run /summary (empty => nobody)
```

## Stack

- Python 3.10+
- python-telegram-bot — bot API
- Telethon — userbot for reading channels/groups
- httpx — HTTP requests (GitHub, RSS)
- anthropic — Claude API for curator logic (v1.5+)
- **core/ pipeline:** postgres+pgvector, sqlalchemy, openai (embeddings + synthesis)
