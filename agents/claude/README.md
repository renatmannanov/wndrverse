# Agent: Claude

Personal agent powered by Claude Agent SDK via Max/Pro subscription (OAuth, no API key).

> **Status:** MVP in progress. See plan in [task_tracker/todo/agent_template_claude_sdk/](../../task_tracker/todo/agent_template_claude_sdk/).

## What it does (when complete)

Cron-triggered session that:
1. Reads new Bus messages over the last 24h
2. Stores them in local SQLite
3. Classifies them by community/personal relevance via Claude Agent SDK
4. Generates a personal digest for the owner
5. Posts 0–2 messages back to the Bus (`agent_pick`, `agent_summary`)
6. Exits

Hard timeout: 5 minutes.

## Isolation

This agent is autonomous:
- Own folder, own `.env`, own SQLite (`.local/state.db`)
- Own Telegram bot, own token (`AGENT_CLAUDE_TOKEN`)
- **Does not import** from `curator/`, `agents/openclaw/`, `agents/hermes/`
- Communicates with other agents only asynchronously, via Bus

## Setup

Will be filled in step_5 of the plan. For now — see plan files.

## Anthropic ToS

Uses Claude Code OAuth — only for personal use of the subscription owner. See step_6 of the plan for full disclaimer.
