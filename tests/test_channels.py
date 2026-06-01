"""Unit tests for delivery.channels.send (stdout + telegram_dm + stubs).

telegram.Bot is faked via monkeypatch — no network, no real token. The fake's
send_message records its call args into a list the test inspects. send() is
called synchronously; asyncio.run inside _send_telegram_dm spins its own loop
on the fake, so no pytest-asyncio is needed (see step_2 note M3).
"""

import sys
import types

import pytest

from delivery import channels


class _FakeBot:
    """Stand-in for telegram.Bot — records send_message calls into `calls`."""
    calls: list = []

    def __init__(self, token):
        self.token = token

    async def send_message(self, *, chat_id, text):
        _FakeBot.calls.append({"token": self.token, "chat_id": chat_id, "text": text})


@pytest.fixture
def fake_telegram(monkeypatch):
    """Install a fake `telegram` module so `from telegram import Bot` returns _FakeBot."""
    _FakeBot.calls = []
    fake_mod = types.ModuleType("telegram")
    fake_mod.Bot = _FakeBot
    monkeypatch.setitem(sys.modules, "telegram", fake_mod)
    monkeypatch.setenv("BOT_TOKEN_INGEST", "TEST_TOKEN")
    monkeypatch.setenv("WNDR_DIGEST_DM_USER_ID", "423915315")
    return _FakeBot


def test_stdout_prints(capsys):
    channels.send("hello", channel="stdout")
    assert capsys.readouterr().out == "hello\n"


def test_telegram_dm_sends_to_env_user(fake_telegram):
    channels.send("digest body", channel="telegram_dm")
    assert len(fake_telegram.calls) == 1
    call = fake_telegram.calls[0]
    assert call["token"] == "TEST_TOKEN"
    assert call["chat_id"] == 423915315
    assert call["text"] == "digest body"


def test_telegram_dm_truncates_over_limit(fake_telegram):
    long_text = "x" * (channels.TELEGRAM_MAX + 500)
    channels.send(long_text, channel="telegram_dm")
    sent = fake_telegram.calls[0]["text"]
    assert len(sent) == channels.TELEGRAM_MAX


def test_telegram_group_not_implemented():
    with pytest.raises(NotImplementedError):
        channels.send("x", channel="telegram_group")


def test_unknown_channel_raises_value_error():
    with pytest.raises(ValueError):
        channels.send("x", channel="bogus")
