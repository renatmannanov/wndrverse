"""
Showcase — постит финальное сообщение куратора в Showcase топик.
"""
import os
from telegram import Bot

CURATOR_BOT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
SHOWCASE_TOPIC_ID = int(os.getenv("SHOWCASE_TOPIC_ID", "0"))


async def post_to_showcase(text: str):
    bot = Bot(token=CURATOR_BOT_TOKEN)
    await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        message_thread_id=SHOWCASE_TOPIC_ID,
        text=text,
    )
