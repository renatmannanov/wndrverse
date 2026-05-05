"""
Claude agent — entrypoint.

Cron-triggered session via Max OAuth (Claude Agent SDK). MVP loop:
1. Verify OAuth session works (ping the SDK with a trivial query)
2. Fetch new Bus messages via Telegram bot
3. Insert into SQLite (idempotent, PK = tg_message_id)
4. Exit

Steps 3 and 4 of the plan add classification, digest, and Bus writeback.

Hard timeout: 5 minutes. If it doesn't finish — kill, exit non-zero, retry next tick.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Force UTF-8 on stdout/stderr (Windows consoles default to cp1252 and mangle non-ASCII)
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

# Hard rule: this agent must NOT use ANTHROPIC_API_KEY.
# If something put it in the system env, drop it BEFORE the SDK looks at env.
os.environ.pop("ANTHROPIC_API_KEY", None)

import bus_client
import state_db

HERE = Path(__file__).parent
DB_PATH = HERE / ".local" / "state.db"
HARD_TIMEOUT_SEC = 300  # 5 minutes

# Exit codes
EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_OAUTH = 3
EXIT_TIMEOUT = 4
EXIT_RUNTIME = 5


def load_config() -> dict:
    load_dotenv(HERE / ".env")
    cfg = {
        "AGENT_CLAUDE_TOKEN": os.getenv("AGENT_CLAUDE_TOKEN", ""),
        "GROUP_CHAT_ID": os.getenv("GROUP_CHAT_ID", ""),
        "BUS_TOPIC_ID": os.getenv("BUS_TOPIC_ID", ""),
        "OWNER_USERNAME": os.getenv("OWNER_USERNAME", ""),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        print(f"[claude-agent] ERROR: missing config: {', '.join(missing)}", file=sys.stderr)
        print(f"[claude-agent] copy .env.example to .env and fill it", file=sys.stderr)
        sys.exit(EXIT_CONFIG)
    cfg["GROUP_CHAT_ID"] = int(cfg["GROUP_CHAT_ID"])
    cfg["BUS_TOPIC_ID"] = int(cfg["BUS_TOPIC_ID"])
    return cfg


async def verify_sdk_session() -> None:
    """
    Ping the SDK to confirm OAuth session is valid.
    On step 2 we don't do real work yet — just make sure `claude login` happened.
    """
    try:
        from claude_agent_sdk import query
    except ImportError:
        print("[claude-agent] ERROR: claude-agent-sdk is not installed", file=sys.stderr)
        print("[claude-agent] run: pip install claude-agent-sdk", file=sys.stderr)
        sys.exit(EXIT_RUNTIME)

    try:
        # Trivial query, just to trigger auth path
        async for _ in query(prompt="reply with the single word: pong"):
            pass
    except Exception as e:
        # Auth failures, network, etc. We don't yet know the exact exception
        # classes from the SDK — catch broadly for MVP, narrow on step 3.
        msg = str(e).lower()
        if "auth" in msg or "login" in msg or "oauth" in msg or "credential" in msg:
            print(f"[claude-agent] ERROR: SDK auth failed — run `claude login`", file=sys.stderr)
            print(f"[claude-agent] details: {e}", file=sys.stderr)
            sys.exit(EXIT_OAUTH)
        print(f"[claude-agent] ERROR: SDK ping failed: {e}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME)


async def fetch_and_store(cfg: dict) -> tuple[int, int]:
    """Returns (fetched_count, inserted_count)."""
    state_db.init_db(DB_PATH)
    last_id = state_db.get_last_seen_message_id(DB_PATH)

    raw_msgs = await bus_client.fetch_bus_updates(
        bot_token=cfg["AGENT_CLAUDE_TOKEN"],
        group_chat_id=cfg["GROUP_CHAT_ID"],
        bus_topic_id=cfg["BUS_TOPIC_ID"],
    )
    new_msgs = bus_client.filter_new(raw_msgs, last_id)

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for m in new_msgs:
        ok = state_db.insert_message(
            DB_PATH,
            tg_message_id=m.tg_message_id,
            posted_at=m.posted_at,
            author=m.author,
            source=m.source,
            text=m.text,
            raw=m.raw,
            seen_at=now,
        )
        if ok:
            inserted += 1

    return len(new_msgs), inserted


async def _run() -> int:
    cfg = load_config()
    print(f"[claude-agent] start — owner=@{cfg['OWNER_USERNAME']}, db={DB_PATH}")

    await verify_sdk_session()
    print(f"[claude-agent] OAuth session OK")

    fetched, inserted = await fetch_and_store(cfg)
    total = state_db.count_messages(DB_PATH)
    print(f"[claude-agent] fetched={fetched} inserted={inserted} total_in_db={total}")

    return EXIT_OK


def main() -> None:
    async def _wrapped() -> int:
        return await asyncio.wait_for(_run(), timeout=HARD_TIMEOUT_SEC)

    try:
        rc = asyncio.run(_wrapped())
    except SystemExit:
        # _run() called sys.exit() — let it propagate with its code
        raise
    except asyncio.TimeoutError:
        print(f"[claude-agent] ERROR: hard timeout {HARD_TIMEOUT_SEC}s exceeded", file=sys.stderr)
        sys.exit(EXIT_TIMEOUT)
    except Exception as e:
        print(f"[claude-agent] ERROR: unhandled: {e}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME)
    sys.exit(rc)


if __name__ == "__main__":
    main()
