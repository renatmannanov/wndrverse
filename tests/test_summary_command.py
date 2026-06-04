"""Unit tests for the /summary command (digest-on-demand step 2).

DB-free, OpenAI-free, Telegram-free:
  - parse_allowed: WNDR_SUMMARY_ALLOWED CSV -> set[int], fail-closed.
  - validate_summary_args: arg count / unknown topic / bad date / from>till.
  - on_summary handler: whitelist denial does NOT call synthesis; a valid call
    reaches build_digest exactly once and DMs the caller.

on_summary is async; driven with asyncio.run (no pytest-asyncio needed).
"""

import asyncio
from types import SimpleNamespace

import pytest

from bot import ingest_bot


# --- parse_allowed ----------------------------------------------------------

def test_parse_allowed_basic():
    assert ingest_bot.parse_allowed("1,2,3") == {1, 2, 3}
    assert ingest_bot.parse_allowed(" 1 , 2 ,3 ") == {1, 2, 3}


def test_parse_allowed_fail_closed():
    assert ingest_bot.parse_allowed(None) == set()
    assert ingest_bot.parse_allowed("") == set()
    assert ingest_bot.parse_allowed("  ") == set()


def test_parse_allowed_skips_garbage():
    assert ingest_bot.parse_allowed("1,foo,2") == {1, 2}


# --- validate_summary_args --------------------------------------------------

def test_validate_good():
    topic, since, until = ingest_bot.validate_summary_args(
        ["questions_to_women", "2026-05-01", "2026-05-31"])
    assert topic == "questions_to_women"
    # inclusive till -> exclusive next-day midnight (see parse_date_range)
    assert (until - since).days == 31


def test_validate_wrong_arg_count():
    with pytest.raises(ingest_bot.SummaryArgError):
        ingest_bot.validate_summary_args(["questions_to_women"])
    with pytest.raises(ingest_bot.SummaryArgError):
        ingest_bot.validate_summary_args([])


def test_validate_unknown_topic():
    with pytest.raises(ingest_bot.SummaryArgError):
        ingest_bot.validate_summary_args(["nope_topic", "2026-05-01", "2026-05-31"])


def test_validate_bad_date():
    with pytest.raises(ingest_bot.SummaryArgError):
        ingest_bot.validate_summary_args(
            ["questions_to_women", "2026-13-99", "2026-05-31"])


def test_validate_from_after_till():
    with pytest.raises(ingest_bot.SummaryArgError):
        ingest_bot.validate_summary_args(
            ["questions_to_women", "2026-05-31", "2026-05-01"])


# --- on_summary handler -----------------------------------------------------

class _FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text))


def _ctx(args, bot=None):
    return SimpleNamespace(args=args, bot=bot or _FakeBot())


def _update(uid):
    msg = _FakeMessage()
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid), message=msg), msg


def test_denied_user_does_not_call_synthesis(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {111})
    called = []
    monkeypatch.setattr(ingest_bot, "count_fragments",
                        lambda *a, **k: called.append(("count",)) or 73)
    monkeypatch.setattr(ingest_bot, "build_digest",
                        lambda *a, **k: called.append(("synth",)) or "x")
    upd, msg = _update(999)  # not whitelisted
    asyncio.run(ingest_bot.on_summary(
        upd, _ctx(["questions_to_women", "2026-05-01", "2026-05-31"])))
    assert called == []                       # neither count nor synth reached
    assert msg.replies and "администратор" in msg.replies[0].lower()


def test_no_args_shows_help(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "get_topics_with_counts",
                        lambda **k: [("questions_to_women", 120)])
    called = []
    monkeypatch.setattr(ingest_bot, "count_fragments",
                        lambda *a, **k: called.append(a) or 0)
    monkeypatch.setattr(ingest_bot, "build_digest",
                        lambda *a, **k: called.append(a))
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_summary(upd, _ctx([])))
    assert called == []
    assert msg.replies and "Формат:" in msg.replies[0]
    assert "questions_to_women (120)" in msg.replies[0]


def test_valid_call_acks_then_dms_clean_digest(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_fragments", lambda *a, **k: 73)
    calls = []
    monkeypatch.setattr(
        ingest_bot, "build_digest",
        lambda topic, since, until: calls.append((topic, since, until))
        or {"text": "DIGEST TEXT", "found": 73, "used": 73})
    bot = _FakeBot()
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_summary(
        upd, _ctx(["questions_to_women", "2026-05-01", "2026-05-31"], bot=bot)))
    assert len(calls) == 1                    # synthesis invoked once
    assert calls[0][0] == "questions_to_women"
    # ack reply: found count + period, sent BEFORE synthesis
    assert msg.replies and "73" in msg.replies[0]
    assert "2026-05-01..2026-05-31" in msg.replies[0]
    # digest: its own DM to the caller, CLEAN (no stats line)
    assert len(bot.sent) == 1
    chat_id, sent_text = bot.sent[0]
    assert chat_id == 7                        # DM'd to the CALLER (uid 7)
    assert sent_text == "DIGEST TEXT"          # clean, no prefix
    assert "Найдено" not in sent_text          # stats stay in the ack only


def test_empty_period_no_spend(monkeypatch):
    """0 fragments -> ack says 'нет', build_digest NEVER called (no OpenAI)."""
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_fragments", lambda *a, **k: 0)
    synth_calls = []
    monkeypatch.setattr(ingest_bot, "build_digest",
                        lambda *a, **k: synth_calls.append(a))
    bot = _FakeBot()
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_summary(
        upd, _ctx(["questions_to_women", "2026-05-01", "2026-05-31"], bot=bot)))
    assert synth_calls == []                    # no OpenAI spend
    assert bot.sent == []                       # no digest sent
    assert msg.replies and "нет" in msg.replies[0].lower()


def test_forbidden_dm_hints_start(monkeypatch):
    from telegram.error import Forbidden

    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_fragments", lambda *a, **k: 5)
    monkeypatch.setattr(ingest_bot, "build_digest",
                        lambda *a, **k: {"text": "TEXT", "found": 5, "used": 5})

    class _ForbidBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            raise Forbidden("blocked")

    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_summary(
        upd, _ctx(["questions_to_women", "2026-05-01", "2026-05-31"], bot=_ForbidBot())))
    # ack (reply 0) + forbidden hint (reply 1)
    assert any("/start" in r for r in msg.replies)
