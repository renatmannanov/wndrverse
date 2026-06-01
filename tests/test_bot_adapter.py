"""Unit tests for core.ingest.bot_adapter.bot_message_to_fragment.

No real Telegram — fake Message/User via SimpleNamespace. Path via conftest.py.
"""

from datetime import datetime
from types import SimpleNamespace

from core.ingest.bot_adapter import bot_message_to_fragment


def _user(uid=42, full_name="Jane Doe", username="jane", is_bot=False):
    return SimpleNamespace(id=uid, full_name=full_name, username=username, is_bot=is_bot)


def _msg(**over):
    base = dict(
        message_id=100,
        chat_id=-1001111111111,
        text="Привет! Ищу со-основателя для community-проекта.",
        caption=None,
        date=datetime(2026, 1, 22, 17, 24, 57),
        from_user=_user(),
        reply_to_message=None,
        message_thread_id=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_basic_text_message():
    f = bot_message_to_fragment(_msg(), topic="men")
    assert f["external_id"] == "tg_-1001111111111_100"   # unified key (NOT tgbot_ / wndr_tgbot_)
    assert f["channel_id"] == -1001111111111
    assert f["topic"] == "men"
    assert f["sender_id"] == 42
    assert f["message_thread_id"] is None
    assert f["text"].startswith("Привет")
    assert f["author_name"] == "Jane Doe"
    assert f["metadata"]["username"] == "jane"


def test_no_text_no_caption_returns_none():
    assert bot_message_to_fragment(_msg(text=None, caption=None), topic="men") is None


def test_service_message_skipped():
    # service messages (joins, title change, pin) carry no text/caption -> None
    assert bot_message_to_fragment(_msg(text=None, caption=None), topic="men") is None


def test_media_with_caption_uses_caption():
    f = bot_message_to_fragment(_msg(text=None, caption="Фото с воркшопа по AI"), topic="men")
    assert f is not None
    assert f["text"] == "Фото с воркшопа по AI"


def test_reply_fills_metadata():
    reply_to = SimpleNamespace(message_id=55)
    f = bot_message_to_fragment(_msg(reply_to_message=reply_to), topic="men")
    assert f["metadata"]["reply_to_msg_id"] == 55


def test_thread_id_passed_through():
    f = bot_message_to_fragment(_msg(message_thread_id=7), topic="deep")
    assert f["message_thread_id"] == 7


def test_anonymous_no_from_user_does_not_crash():
    f = bot_message_to_fragment(_msg(from_user=None), topic="men")
    assert f is not None
    assert f["sender_id"] is None
    assert f["author_name"] is None
    assert f["metadata"]["username"] is None
