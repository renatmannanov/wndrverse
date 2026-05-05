# Claude agent

Lives in a separate repo for independent deployment.

→ **https://github.com/renatmannanov/wndrverse_agent_claude**

## Why a separate repo

Each agent in the wndrverse network is autonomous: own code, own deployment, own bot, own state. Keeping them in separate repos means each can be deployed to its own machine without dragging the rest of the project along.

## Plan and design notes

The plan, ToS rationale, and step-by-step build log live in this parent repo:

- [task_tracker/todo/agent_template_claude_sdk/](../../task_tracker/todo/agent_template_claude_sdk/) — full plan
- [bus-protocol.md](../../bus-protocol.md) — Bus message format (the contract this agent implements)
- [members.json](../../members.json) — community members registry (snapshot copied into the agent repo)

## Predecessor

Earlier scaffold lived directly in this folder. After being moved to the standalone repo, that scaffold was archived in [`../_claude/`](../_claude/) — kept on disk for reference, prefix `_` marks it as deprecated and not to be run.
