"""Realtime ingest bot: python-telegram-bot (polling) -> core ingest().

Long-lived process. Each new message from a mapped chat becomes one Fragment
and is written to the DB via the same funnel as the file loader.

Run (module form only — `python bot/ingest_bot.py` breaks `core.*` imports):
    python -m bot.ingest_bot
"""

import asyncio
import logging
import os

from telegram.ext import Application, MessageHandler, filters

from core.ingest.loaders import ingest
from core.ingest.bot_adapter import bot_message_to_fragment
from core.ingest.topic_map import resolve_topic

logger = logging.getLogger(__name__)


async def on_message(update, context):
    msg = update.effective_message
    if msg is None:
        return

    # don't ingest our own or other bots' messages
    if msg.from_user and msg.from_user.is_bot:
        return

    topic = resolve_topic(msg.chat_id, msg.message_thread_id)
    if topic is None:
        logger.info("skip: no topic for chat=%s thread=%s", msg.chat_id, msg.message_thread_id)
        return

    frag = bot_message_to_fragment(msg, topic=topic)
    if frag is None:
        return  # empty / service message

    # ingest() is synchronous (hits the DB) — run off the event loop.
    # try/except: a DB failure must not kill the handler; log the lost message
    # and keep the bot alive.
    try:
        res = await asyncio.to_thread(ingest, [frag])
        logger.info("ingest chat=%s msg=%s topic=%s -> %s",
                    msg.chat_id, msg.message_id, topic, res)
    except Exception:
        logger.exception("ingest FAILED chat=%s msg=%s topic=%s (message lost)",
                         msg.chat_id, msg.message_id, topic)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from dotenv import load_dotenv
        load_dotenv()  # BOT_TOKEN_INGEST / WNDR_TOPIC_MAP / DATABASE_URL from .env
    except ImportError:
        pass

    token = os.environ["BOT_TOKEN_INGEST"]
    app = Application.builder().token(token).build()
    # content messages; service updates (joins/leaves/title/pin) are filtered out
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
