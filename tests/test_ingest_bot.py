"""Unit tests for bot.ingest_bot.on_message (the handler), no real Telegram.

on_message is async; we drive it with asyncio.run so the test needs no
pytest-asyncio config. ingest is patched to record calls instead of hitting the DB.
Path via conftest.py.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

from bot import ingest_bot


def _user(uid=42, is_bot=False):
    return SimpleNamespace(id=uid, full_name="Jane Doe", username="jane", is_bot=is_bot)


def _msg(**over):
    base = dict(
        message_id=100,
        chat_id=-1001111111111,
        text="Содержательное сообщение для ingest, длиннее порога.",
        caption=None,
        date=datetime(2026, 1, 22, 17, 24, 57),
        from_user=_user(),
        reply_to_message=None,
        message_thread_id=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _update(msg):
    return SimpleNamespace(effective_message=msg)


def _run_handler(monkeypatch, msg, topic):
    """Patch resolve_topic + ingest, run on_message, return list of ingest calls."""
    calls = []
    monkeypatch.setattr(ingest_bot, "resolve_topic", lambda chat, thread: topic)
    monkeypatch.setattr(ingest_bot, "ingest",
                        lambda frags: calls.append(frags) or {"indexed": len(frags),
                                                               "duplicates_skipped": 0})
    asyncio.run(ingest_bot.on_message(_update(msg), context=None))
    return calls


def test_mapped_message_is_ingested(monkeypatch):
    calls = _run_handler(monkeypatch, _msg(), topic="men")
    assert len(calls) == 1
    (frags,) = calls
    assert len(frags) == 1
    assert frags[0]["external_id"] == "tg_-1001111111111_100"
    assert frags[0]["topic"] == "men"
    assert frags[0]["channel_id"] == -1001111111111


def test_unmapped_chat_not_ingested(monkeypatch):
    calls = _run_handler(monkeypatch, _msg(), topic=None)   # resolve_topic -> None
    assert calls == []


def test_empty_message_not_ingested(monkeypatch):
    calls = _run_handler(monkeypatch, _msg(text=None, caption=None), topic="men")
    assert calls == []   # adapter returns None -> no ingest


def test_bot_message_not_ingested(monkeypatch):
    # step_4: messages from bots (incl. our own) are dropped before resolve_topic
    calls = _run_handler(monkeypatch, _msg(from_user=_user(is_bot=True)), topic="men")
    assert calls == []


def test_no_effective_message_not_ingested(monkeypatch):
    calls = []
    monkeypatch.setattr(ingest_bot, "resolve_topic", lambda c, t: "men")
    monkeypatch.setattr(ingest_bot, "ingest", lambda frags: calls.append(frags))
    asyncio.run(ingest_bot.on_message(SimpleNamespace(effective_message=None), context=None))
    assert calls == []
