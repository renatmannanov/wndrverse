# Archived: early Claude agent scaffold

> **DEPRECATED.** Underscore prefix marks this folder as archived. Do not run from here.

The active Claude agent now lives in a separate repository:
**https://github.com/renatmannanov/wndrverse_agent_claude**

See [../claude/README.md](../claude/README.md) for the redirect note.

## What's preserved here

- `main.py`, `bus_client.py`, `state_db.py` — the original step_2 scaffold
- `.env`, `.local/state.db` — local test artifacts (gitignored, will not push)
- `.env.example`, `.gitignore`, `prompts/` — original project files

These are kept on disk in case any debugging needs to inspect what the first working version looked like (e.g. how the test message at msg_id=60 was parsed). Once the standalone repo proves stable in production, this folder can be safely deleted.

## Why archived, not deleted

`git mv` preserves history (you can `git log --follow` to trace), but the working files were also kept on disk to make local inspection easy without checking out an old commit.
