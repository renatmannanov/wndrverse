"""
Bus client for the Claude agent.

Step 2 (this step): read-only — fetch recent messages from Bus topic.
Step 4 (later):    will add post() to write agent_pick / agent_summary.

Reads via python-telegram-bot. The bot must:
- be a member of the supergroup
- have permission to read the Bus topic

Caveat: Telegram Bot API does NOT expose arbitrary chat history to bots.
A bot only sees messages it received via getUpdates (since it joined / since
last poll). For backfill of older Bus history we'd need Telethon (userbot mode)
or the community DB — both out of scope for MVP.

Strategy for MVP:
- run getUpdates with a long offset window
- filter messages: chat_id == GROUP_CHAT_ID, message_thread_id == BUS_TOPIC_ID
- parse [author|source] header
- skip anything that doesn't match the format
"""
import re
from dataclasses import dataclass
from typing import Iterable

from telegram import Bot, Update

# Format: [author|source] text
_HEADER_RE = re.compile(r"^\[([^\|\]]+)\|([^\|\]]+)\]\s+(.+)$", re.DOTALL)


@dataclass
class BusMessage:
    tg_message_id: int
    posted_at: str  # ISO timestamp
    author: str
    source: str
    text: str
    raw: str  # full original "[a|s] text"


def parse_bus_message(raw: str) -> tuple[str, str, str] | None:
    """Parse '[author|source] text' header. Returns (author, source, text) or None."""
    if not raw:
        return None
    m = _HEADER_RE.match(raw.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()


async def fetch_bus_updates(
    bot_token: str,
    group_chat_id: int,
    bus_topic_id: int,
) -> list[BusMessage]:
    """
    Fetch recent updates and return parsed Bus messages from the right topic.

    Uses long getUpdates poll. Doesn't track offset — caller is expected to
    deduplicate via SQLite (PK on tg_message_id).
    """
    bot = Bot(token=bot_token)
    updates: list[Update] = await bot.get_updates(timeout=10, allowed_updates=["message"])

    out: list[BusMessage] = []
    for upd in updates:
        msg = upd.message
        if msg is None:
            continue
        if msg.chat_id != group_chat_id:
            continue
        if msg.message_thread_id != bus_topic_id:
            continue

        text = msg.text or msg.caption or ""
        parsed = parse_bus_message(text)
        if parsed is None:
            continue
        author, source, body = parsed

        out.append(
            BusMessage(
                tg_message_id=msg.message_id,
                posted_at=msg.date.isoformat() if msg.date else "",
                author=author,
                source=source,
                text=body,
                raw=text,
            )
        )

    return out


def filter_new(messages: Iterable[BusMessage], since_id: int | None) -> list[BusMessage]:
    """Keep messages with tg_message_id > since_id (or all if since_id is None)."""
    if since_id is None:
        return list(messages)
    return [m for m in messages if m.tg_message_id > since_id]
