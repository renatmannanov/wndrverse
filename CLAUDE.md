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

## Key files

- `members.json` — list of participants and their sources
- `bus-protocol.md` — message format for the Bus
- `task_tracker/todo/PLAN.md` — current development plan
- `task_tracker/todo/ARCHITECTURE.md` — full architecture decisions

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
