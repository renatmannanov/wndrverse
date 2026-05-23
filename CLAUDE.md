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
| `renatmannanov/wndrverse` | this repo (was `re_verse`, renamed 2026-05) — main: plans, curator, docs | local `~/projects/wndrverse` |
| `renatmannanov/wndrverse_agent_claude` | Claude agent, extracted to standalone (commit 7f61088) — **this is what's deployed** | VPS `~/wndrverse_agent_claude` (migrating to `~/claude-hub/projects/wndrverse`) |
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
PII: only text + `[#id]` go to OpenAI; names substituted locally on output.
`data/` is gitignored — community messages are never committed.

## Key files

- `members.json` — list of participants and their sources
- `bus-protocol.md` — message format for the Bus
- `task_tracker/todo/PLAN.md` — current development plan
- `task_tracker/todo/ARCHITECTURE.md` — full architecture decisions
- `core/` — community brain (digest pipeline): db / ingest / store / enrich / brain / llm / prompts
- `delivery/` — digest CLI + output channels (stdout now; telegram = future)
- `docker-compose.yml` — postgres+pgvector (db `wndrverse`, port 5434)

## Env vars

```
BOT_TOKEN          — Telegram bot token (@BotFather)
BUS_CHAT_ID        — Telegram supergroup ID (Bus topic)
MY_USERNAME        — your Telegram username
TG_CHANNEL         — your public TG channel username
GITHUB_USERNAME    — your GitHub username
ANTHROPIC_API_KEY  — for Option B (Claude Managed Agent)
```

## Stack

- Python 3.10+
- python-telegram-bot — bot API
- Telethon — userbot for reading channels/groups
- httpx — HTTP requests (GitHub, RSS)
- anthropic — Claude API for curator logic (v1.5+)
- **core/ pipeline:** postgres+pgvector, sqlalchemy, openai (embeddings + synthesis)
