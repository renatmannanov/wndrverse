"""The core guarantee of the data-corpus plan (step 1): the file backfill and the
realtime bot produce the SAME external_id for the same (chat_id, msg_id).

Dedup in core.store.fragments_db is a per-row SELECT on external_id (not ON
CONFLICT), so the keys must match byte-for-byte or the same message doubles.
This test pins both paths to `tg_{chat_id}_{msg_id}`. Path via conftest.py.
"""

from datetime import datetime
from types import SimpleNamespace

from core.ingest.normalize import message_to_fragment
from core.ingest.bot_adapter import bot_message_to_fragment

CHAT_ID = -1002924475859
MSG_ID = 4242


def test_backfill_and_bot_produce_same_external_id():
    # file backfill path (telethon export -> normalize, now carrying chat_id)
    backfill = message_to_fragment(
        {"id": MSG_ID, "text": "hi", "date": "2026-01-22T17:24:57"},
        topic="offerings", chat_name="WNDR chat",
        chat_id=CHAT_ID, thread_root_id=None,
    )

    # realtime bot path (PTB Message -> bot_adapter)
    bot_msg = SimpleNamespace(
        message_id=MSG_ID, chat_id=CHAT_ID, text="hi", caption=None,
        date=datetime(2026, 1, 22, 17, 24, 57),
        from_user=SimpleNamespace(id=1, full_name="X", username="x", is_bot=False),
        reply_to_message=None, message_thread_id=None,
    )
    bot = bot_message_to_fragment(bot_msg, topic="offerings")

    assert backfill["external_id"] == bot["external_id"] == f"tg_{CHAT_ID}_{MSG_ID}"
    assert backfill["channel_id"] == bot["channel_id"] == CHAT_ID
