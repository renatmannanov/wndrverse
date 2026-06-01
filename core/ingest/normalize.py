"""
Normalize telegram-gather messages into Fragment dicts.

One message → one Fragment. This is the single mapping point; a future realtime
source (bot/telethon) produces the same {msg} shape and reuses this.
"""

from datetime import datetime


def _extract_tags(text: str) -> list[str]:
    """Hashtags from text. (ayda had no _extract_tags in code — written here.)"""
    return [w.lstrip('#') for w in text.split() if w.startswith('#') and len(w) > 1]


def message_to_fragment(
    msg: dict,
    *,
    topic: str,
    chat_name: str,
    chat_id: int | None = None,
    thread_root_id: int | None,
) -> dict | None:
    """Map one telegram-gather message to a Fragment dict.

    Returns None for service/empty messages (no text) — they are skipped.
    created_at is a datetime object here (insert_fragments_batch takes datetime;
    it becomes a string only on the way OUT of query functions).

    external_id is the dedup key (per-message, must match byte-for-byte across the
    file backfill and the realtime bot). When chat_id is known we use the unified
    `tg_{chat_id}_{msg_id}` form; legacy file exports without chat_id fall back to
    the old `wndr_{chat_name}_{msg_id}` key.
    """
    text = msg.get('text')
    if not text or not text.strip():
        return None

    if chat_id is not None:
        external_id = f"tg_{chat_id}_{msg['id']}"
    else:
        external_id = f"wndr_{chat_name}_{msg['id']}"  # legacy (old exports w/o chat_id)

    return {
        'external_id': external_id,               # dedup across runs / sources
        'source': 'telegram',
        'text': text,
        'created_at': datetime.fromisoformat(msg['date']),
        'tags': _extract_tags(text),
        'content_type': 'note',
        'sender_id': msg.get('user_id'),          # may be None — don't crash
        'author_name': msg.get('sender_name'),
        'topic': topic,
        'channel_id': chat_id,                    # backfill previously left this unset
        'message_thread_id': thread_root_id,
        'metadata': {
            'username': msg.get('username'),
            'reactions': msg.get('reactions'),
            'char_count': msg.get('char_count'),
            'reply_to_msg_id': msg.get('reply_to_msg_id'),
        },
    }
