"""
Bus — постит сообщения агентов в Bus топик Telegram.
"""
import os
from telegram import Bot, Message

CURATOR_BOT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
BUS_TOPIC_ID = int(os.getenv("BUS_TOPIC_ID", "0"))

_posted_keys: set[str] = set()


async def post_to_bus(
    text: str,
    bot_token: str | None = None,
    key: str | None = None,
) -> Message | None:
    """
    Постит текст в Bus топик.
    bot_token — токен бота-агента (если None — используется CURATOR_BOT_TOKEN).
    key — уникальный ключ для дедупликации (agent_name + date + text hash).
    """
    if not key:
        key = str(hash(text))
    if key in _posted_keys:
        print(f"  skip duplicate: {key}")
        return None

    token = bot_token or CURATOR_BOT_TOKEN
    bot = Bot(token=token)
    msg = await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        message_thread_id=BUS_TOPIC_ID,
        text=text,
    )

    _posted_keys.add(key)
    return msg


async def reply_in_bus(
    text: str,
    reply_to_message_id: int,
    bot_token: str | None = None,
) -> Message:
    """
    Отправляет реплай на сообщение в Bus топике.
    """
    token = bot_token or CURATOR_BOT_TOKEN
    bot = Bot(token=token)
    return await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        message_thread_id=BUS_TOPIC_ID,
        text=text,
        reply_to_message_id=reply_to_message_id,
    )
