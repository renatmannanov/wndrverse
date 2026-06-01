"""Adapt a python-telegram-bot Message into a Fragment dict.

Reuses core.ingest.normalize.message_to_fragment (the single mapping point) —
this module only (a) flattens the PTB Message into the dict normalize expects,
(b) overwrites external_id with the bot-scoped key, (c) fills channel_id (which
normalize leaves unset, since the file path never had a chat_id).
"""

from core.ingest.normalize import message_to_fragment


def bot_message_to_fragment(message, *, topic: str) -> dict | None:
    """telegram.Message (PTB) -> Fragment dict, via normalize.message_to_fragment.

    Returns None for empty/service messages (no text and no caption).
    """
    from_user = message.from_user
    text = message.text or message.caption  # caption = text of media-with-caption

    flat = {
        "id": message.message_id,
        "text": text,
        "date": message.date.isoformat(),  # PTB gives datetime; normalize wants ISO string
        "user_id": from_user.id if from_user else None,
        "sender_name": from_user.full_name if from_user else None,
        "username": from_user.username if from_user else None,
        "reply_to_msg_id": (
            message.reply_to_message.message_id if message.reply_to_message else None
        ),
        "char_count": len(text) if text else None,
    }

    frag = message_to_fragment(
        flat,
        topic=topic,
        chat_name="tgbot",                       # only affects external_id (overwritten below)
        thread_root_id=message.message_thread_id,
    )
    if frag is None:
        return None  # no text/caption -> skip

    # Overwrite both fields for a bot source — same unified key as the file
    # backfill so the same (chat_id, msg_id) dedups to ONE row regardless of path:
    #  - external_id: `tg_{chat_id}_{msg_id}` (chat_id MUST be in the key —
    #    message_id collides across chats). Replaces normalize's "wndr_tgbot_{id}".
    #  - channel_id: normalize was called without chat_id here, so set it now.
    frag["external_id"] = f"tg_{message.chat_id}_{message.message_id}"
    frag["channel_id"] = message.chat_id
    return frag
