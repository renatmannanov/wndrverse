"""Unit tests for the /topics command (hot-topics digest on demand).

DB-free, OpenAI-free, Telegram-free:
  - validate_topics_args: arg count / unknown topic / 'all' / bad date /
    from>till / bad limit / default limit.
  - on_topics handler: whitelist denial calls neither count nor build; a valid
    call acks first and reaches build_topics_digest exactly once, DMing the
    caller a clean digest.

on_topics is async; driven with asyncio.run (no pytest-asyncio needed).
"""

import asyncio
from types import SimpleNamespace

import pytest

from bot import ingest_bot


# --- validate_topics_args -----------------------------------------------------

def test_validate_good_3_args_default_limit():
    topic, since, until, limit = ingest_bot.validate_topics_args(
        ["boltalka", "2026-05-01", "2026-05-31"])
    assert topic == "boltalka"
    # inclusive till -> exclusive next-day midnight (see parse_date_range)
    assert (until - since).days == 31
    assert limit == ingest_bot.DEFAULT_TOPICS_LIMIT


def test_validate_good_4_args_explicit_limit():
    topic, since, until, limit = ingest_bot.validate_topics_args(
        ["boltalka", "2026-05-01", "2026-05-31", "3"])
    assert topic == "boltalka"
    assert limit == 3


@pytest.mark.parametrize("args", [
    [],
    ["boltalka"],
    ["boltalka", "2026-05-01"],
    ["boltalka", "2026-05-01", "2026-05-31", "3", "extra"],
])
def test_validate_wrong_arg_count(args):
    with pytest.raises(ingest_bot.TopicsArgError):
        ingest_bot.validate_topics_args(args)


def test_validate_unknown_topic():
    with pytest.raises(ingest_bot.TopicsArgError):
        ingest_bot.validate_topics_args(["nope_topic", "2026-05-01", "2026-05-31"])


def test_validate_all_topic_rejected():
    with pytest.raises(ingest_bot.TopicsArgError):
        ingest_bot.validate_topics_args(["all", "2026-05-01", "2026-05-31"])


def test_validate_bad_date():
    with pytest.raises(ingest_bot.TopicsArgError):
        ingest_bot.validate_topics_args(["boltalka", "2026-13-99", "2026-05-31"])


def test_validate_from_after_till():
    with pytest.raises(ingest_bot.TopicsArgError):
        ingest_bot.validate_topics_args(["boltalka", "2026-05-31", "2026-05-01"])


@pytest.mark.parametrize("bad_limit", ["foo", "0", "-3"])
def test_validate_bad_limit(bad_limit):
    with pytest.raises(ingest_bot.TopicsArgError):
        ingest_bot.validate_topics_args(
            ["boltalka", "2026-05-01", "2026-05-31", bad_limit])


# --- on_topics handler --------------------------------------------------------

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


def test_denied_user_calls_nothing(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {111})
    called = []
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: called.append(("count",)) or 73)
    monkeypatch.setattr(ingest_bot, "build_topics_digest",
                        lambda *a, **k: called.append(("build",)) or "x")
    upd, msg = _update(999)  # not whitelisted
    asyncio.run(ingest_bot.on_topics(
        upd, _ctx(["boltalka", "2026-05-01", "2026-05-31"])))
    assert called == []                       # neither count nor build reached
    assert msg.replies and "администратор" in msg.replies[0].lower()


def test_no_args_shows_help(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "get_topics_with_counts",
                        lambda **k: [("boltalka", 4242)])
    called = []
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: called.append(a) or 0)
    monkeypatch.setattr(ingest_bot, "build_topics_digest",
                        lambda *a, **k: called.append(a))
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_topics(upd, _ctx([])))
    assert called == []
    assert msg.replies and "Формат:" in msg.replies[0]
    assert "boltalka (4242)" in msg.replies[0]


def test_valid_call_acks_then_dms_clean_digest(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: 73)
    calls = []
    monkeypatch.setattr(
        ingest_bot, "build_topics_digest",
        lambda topic, since, until, limit: calls.append((topic, since, until, limit))
        or {"text": "TOPICS TEXT", "found": 73})
    bot = _FakeBot()
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_topics(
        upd, _ctx(["boltalka", "2026-05-01", "2026-05-31"], bot=bot)))
    assert len(calls) == 1                    # build invoked once
    assert calls[0][0] == "boltalka"
    assert calls[0][3] == ingest_bot.DEFAULT_TOPICS_LIMIT
    # ack reply: found count + period, sent BEFORE the build
    assert msg.replies and "73" in msg.replies[0]
    assert "2026-05-01..2026-05-31" in msg.replies[0]
    # digest: its own DM to the caller, CLEAN (no stats line)
    assert len(bot.sent) == 1
    chat_id, sent_text = bot.sent[0]
    assert chat_id == 7                        # DM'd to the CALLER (uid 7)
    assert sent_text == "TOPICS TEXT"          # clean, no prefix
    assert "Найдено" not in sent_text          # stats stay in the ack only


def test_explicit_limit_passed_through(monkeypatch):
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: 73)
    calls = []
    monkeypatch.setattr(
        ingest_bot, "build_topics_digest",
        lambda topic, since, until, limit: calls.append(limit)
        or {"text": "T", "found": 73})
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_topics(
        upd, _ctx(["boltalka", "2026-05-01", "2026-05-31", "3"])))
    assert calls == [3]


def test_empty_period_no_spend(monkeypatch):
    """0 fragments -> ack says 'нет', build_topics_digest NEVER called (no OpenAI)."""
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: 0)
    build_calls = []
    monkeypatch.setattr(ingest_bot, "build_topics_digest",
                        lambda *a, **k: build_calls.append(a))
    bot = _FakeBot()
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_topics(
        upd, _ctx(["boltalka", "2026-05-01", "2026-05-31"], bot=bot)))
    assert build_calls == []                    # no OpenAI spend
    assert bot.sent == []                       # no digest sent
    assert msg.replies and "нет" in msg.replies[0].lower()


def test_zero_topics_sends_explanatory_text(monkeypatch):
    """found>0 but all themes flood-filtered -> the explanatory text IS DM'd."""
    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: 12)
    monkeypatch.setattr(
        ingest_bot, "build_topics_digest",
        lambda *a, **k: {"text": "📅 hdr\n\nЗа период тем не найдено (всё отсеяно как флуд/шум).",
                         "found": 12})
    bot = _FakeBot()
    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_topics(
        upd, _ctx(["boltalka", "2026-05-01", "2026-05-31"], bot=bot)))
    assert len(bot.sent) == 1
    assert "тем не найдено" in bot.sent[0][1]


def test_forbidden_dm_hints_start(monkeypatch):
    from telegram.error import Forbidden

    monkeypatch.setattr(ingest_bot, "ALLOWED", {7})
    monkeypatch.setattr(ingest_bot, "count_embedded_fragments_for_period",
                        lambda *a, **k: 5)
    monkeypatch.setattr(ingest_bot, "build_topics_digest",
                        lambda *a, **k: {"text": "TEXT", "found": 5})

    class _ForbidBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            raise Forbidden("blocked")

    upd, msg = _update(7)
    asyncio.run(ingest_bot.on_topics(
        upd, _ctx(["boltalka", "2026-05-01", "2026-05-31"], bot=_ForbidBot())))
    # ack (reply 0) + forbidden hint (reply 1)
    assert any("/start" in r for r in msg.replies)
