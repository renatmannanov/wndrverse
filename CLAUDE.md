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

### Hot-topics digest (delivery topics) — experimental, variant A

```bash
python -m delivery topics --topic boltalka --period 1m [--channel stdout] [--limit N]
```

A SECOND, experimental digest mode, parallel to the people-grouping digest (which
it does NOT touch). Takes messages of ONE topic over a period, glues them into
reply-thread DOCUMENTS, clusters the documents by meaning (existing embeddings +
UMAP→HDBSCAN), ranks themes by "hotness" (msgs+likes+authors) and renders
`emoji + name + (N сообщений)` / an `intrigue` hook line / `t.me link`. `--topic
all` is rejected (variant A is single-topic; cross-topic = future).

Pipeline: `get_embedded_fragments_for_period` (store) → `build_chains`
(core/brain/chains.py) → `build_topics` (core/brain/topics.py) → `topics_render`
(delivery) → CLI. `build_chains` (2026-06-10) merges reply links
(`metadata.reply_to_msg_id`, string-compared with the `external_id` digit tail)
plus series — consecutive messages of ONE author ≤300s apart, per-SENDER
adjacency, so interleaved other-author messages don't break a longread series;
EXCEPTION: two messages replying to DIFFERENT parents are never series-linked
(the author answers two conversations, not continues one — otherwise orphan
replies to uningested media messages glue into frankendocs). Document embedding
= length-weighted mean of its substantive message vectors (no re-embedding;
`_is_substantive` lives in chains.py, re-exported by topics.py). In the
rendered digest `N сообщений` counts only substantive messages, but
likes/authors of short reactions DO feed hotness
(`hotness.chain_cluster_stats`). Link anchor = the `root` (earliest SUBSTANTIVE
message, so a short reaction can't be the link target) of the earliest
tightly-attached document. Replies whose parent is NOT in the corpus (media
without text is never ingested; pre-period parents) become chain roots by
design — such an anchor can read mid-context. The pure clustering core is
`cluster_embeddings` in `core/brain/clustering.py` (shared with corpus
`run_clustering`); it falls back to UMAP `init='random'` on small slices to dodge
the spectral-init `eigsh k>=N` crash. Calibrated thresholds (min_chars=80,
min_cluster_size=2 — recalibrated 2026-06-10 for document clustering,
min_authors=2, min_probability=0.05) live in `build_topics` with a comment. LLM
labels use `core/prompts/topic_label.md` (2026-06-18): ONE call returns a JSON
object `{"name","intrigue"}` — a 2-5-word title + a one-line hook (≤140 chars,
a question/conflict, not a recap; the prompt carries a good/bad few-shot).
`build_topics` parses it with a dedicated tolerant OBJECT parser (`_parse_label_obj`,
NOT synthesis `_parse_json_array` which hunts for `[`/`]`), `max_tokens=200` (30
clipped the Cyrillic intrigue), model = `COMPLETION_MODEL` (gpt-4o-mini); fail-soft
to `name="тема", intrigue=""` on any parse/LLM error. Topic dict gains an `intrigue`
key; `render_topics` prints the hook line between name and link via `.get` (empty/
absent → old format). PII stays local (only message text → OpenAI, names/sender_id
never leave). A narrow 1-week slice
may yield few/zero topics by design (little data after the flood-filter). Output:
stdout (CLI) or the ingest bot's `/topics` command (DM, see below). The shared
core is `delivery.cli.build_topics_digest` (store → build_topics → render_topics
→ `{'text','found'}`, or None on 0 fragments) — used by both CLI and bot. A
scheduler / posting straight to the group topic are still out of scope.

### Realtime ingest bot (bot/) — live group → fragments

```bash
python -m bot.ingest_bot                             # polling listener (long-lived); module form only
```

Writes new group messages into `fragments` in realtime via the same `ingest()`
funnel as the file loader. Needs `BOT_TOKEN_INGEST` (separate bot, privacy mode
OFF) and a `core/ingest/topic_map.json` mapping `(chat_id, thread_id) → topic`
(gitignored — holds real chat_ids; copy from `topic_map.example.json`).
Unknown chats are skipped + logged. Run on Windows with `PYTHONUTF8=1` if the
console mangles Cyrillic. **boltalka = the forum's «General» topic → its messages
arrive with `message_thread_id=None`, so its row MUST be `thread_id: null` (the
per-channel fallback `(chat_id, None)` catches it). Do NOT "fix" it back to a
number (was `1` → silent skip «no topic», dropped 4–18 Jun until
`fix-boltalka-ingest` 2026-06-18). Other topics carry their own non-null
thread_id and aren't touched by the fallback.**

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

The bot also serves `/topics <topic> <YYYY-MM-DD> <YYYY-MM-DD> [limit]` — the
hot-topics digest (see section above) over an EXACT date range, same shape as
`/summary`: same whitelist `WNDR_SUMMARY_ALLOWED` (no separate env), no-args →
format help + topic list, ack via cheap `count_embedded_fragments_for_period`
BEFORE any OpenAI spend, then the rendered themes as a clean separate DM.
`limit` is the optional top-N themes (default 10); `all` topic is rejected
(variant A is single-topic). found>0 but every theme flood-filtered → an
explanatory "тем не найдено" DM, distinct from "нет сообщений".

Synthesis (`core/brain/synthesis.py`): for ≤ `MAX_FRAGMENTS_WITHOUT_SELECTION`
(=150) fragments the whole period is fed to the model in one pass; above that a
Pass-1 LLM selection trims to ~20 (now over FULL text, not 100-char previews).
The 150 threshold + full-text selection came from a 2026-06-04 A/B/C test:
synthesizing all messages of a monthly range beat selection (more themes, cheaper).

**Digest output quality** (2026-06-18, `task_tracker/done/digest-output-quality/`):
Pass-2 synthesis runs on **gpt-4o** (Pass-1 selection stays gpt-4o-mini) —
constant `COMPLETION_MODEL_SYNTHESIS`, settable via env `WNDR_SYNTHESIS_MODEL`
(default gpt-4o) for A/B without a code change. `max_tokens` for Pass-2 is
`SYNTHESIS_MAX_TOKENS=3200` (Cyrillic is token-expensive; 2200 clipped long
digests); `_looks_truncated` logs a warning when output doesn't end on terminal
punctuation (signal only, no retry). `min_chars` for digest eligibility is **80**
(was 150) in `get_fragments_for_digest` + `get_topics_with_counts` — short offers/
requests now reach synthesis (hot-topics `get_embedded_fragments_for_period` keeps
min_chars=1). CAVEAT found in testing: a topic that crosses 150 at the new threshold
trips Pass-1 selection (used≈20), which can SHORTEN its digest — revisit
`MAX_FRAGMENTS_WITHOUT_SELECTION` if that bites. An optional **self-critic Pass-3**
(`_critique`, prompt `core/prompts/digest_critic.md`) validates the digest vs its
sources and logs defects WITHOUT rewriting — OFF by default, enable with
`WNDR_DIGEST_CRITIC` truthy. It runs on `[@N]`-form text (PII-safe), is fail-soft
(unparseable→[]), and `result['critic_issues']` rides through `build_digest`. Note:
the gpt-4o critic is noisy (false positives on `[@N]` numbers) — useful as a signal,
not gospel. **Known limitation (NOT fixed here):** dedup `is_duplicate` is set only
by `core/enrich/embedder.py` on a 6h timer, so a fresh-period digest can see near-
dupes as distinct (up to 6h lag). Golden-set regression: `python -m tests.golden.run`
(snapshots are PII, gitignored; `--baseline` captures pre-change output).

**Richer themes** (2026-06-18, `task_tracker/done/digest-richer-themes/`): the
«📌 ГЛАВНЫЕ ТЕМЫ» block of `/summary` now asks (in `digest_synthesis.md`) for a
short title + 1-2 sentences of substance per theme (what was discussed / where it
landed / the disagreement) instead of a bare one-liner; «КТО ЧТО» and «ЗАПРОСЫ»
are untouched. The `[@N]` ban inside the themes block stays; the prompt makes
explicit that theme substance must fit WITHIN the ~2800/≤3500 budget, not add on
top. Local smoke: questions_to_women monthly digest ≈3231 chars — close to the
3500 cap on participant-heavy topics, watch for overflow (still under). Same task
also added the `/topics` intrigue hook (see Hot-topics section above).

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
The venv also needs `requirements-clustering.txt` (umap-learn + hdbscan,
installed 2026-06-10) — `/topics` imports them lazily inside the handler, so a
missing install does NOT fail at bot startup, only at the first /topics call.

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
WNDR_SUMMARY_ALLOWED — CSV of Telegram user_ids allowed to run /summary AND /topics (empty => nobody)
WNDR_SYNTHESIS_MODEL — digest Pass-2 synthesis model (default gpt-4o; A/B without a code change)
WNDR_DIGEST_CRITIC — enable digest self-critic Pass-3 (truthy=on; default OFF, +1 LLM call, noisy)
```

## Stack

- Python 3.10+
- python-telegram-bot — bot API
- Telethon — userbot for reading channels/groups
- httpx — HTTP requests (GitHub, RSS)
- anthropic — Claude API for curator logic (v1.5+)
- **core/ pipeline:** postgres+pgvector, sqlalchemy, openai (embeddings + synthesis)
