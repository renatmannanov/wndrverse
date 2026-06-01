"""
Delivery channels. MVP: stdout + telegram_dm. telegram_group is a future stub.
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

TELEGRAM_MAX = 4096


def send(text: str, *, channel: str = "stdout") -> None:
    """Send ready text to a channel.

    'stdout' (print) and 'telegram_dm' (bot → user's DM) are implemented.
    'telegram_group' is a future feature.
    """
    if channel == "stdout":
        print(text)
    elif channel == "telegram_dm":
        _send_telegram_dm(text)
    elif channel == "telegram_group":
        raise NotImplementedError("channel 'telegram_group' is a future feature")
    else:
        raise ValueError(f"unknown channel: {channel}")


def _send_telegram_dm(text: str) -> None:
    """Send text to a user's DM via BOT_TOKEN_INGEST.

    Sync-only: called from the synchronous scheduler (time.sleep loop), not from
    an async handler — python-telegram-bot v22 is async-only, so we drive a short
    asyncio.run(...) here.

    Safety truncation to 4096 (Telegram's hard limit) is the second length layer;
    the first (soft) layer is the synthesis prompt + max_tokens.
    """
    from telegram import Bot

    token = os.environ["BOT_TOKEN_INGEST"]
    user_id = int(os.environ["WNDR_DIGEST_DM_USER_ID"])
    if len(text) > TELEGRAM_MAX:
        logger.warning("digest %d chars > %d, truncating", len(text), TELEGRAM_MAX)
        text = text[:TELEGRAM_MAX]

    async def _go():
        bot = Bot(token)
        await bot.send_message(chat_id=user_id, text=text)

    asyncio.run(_go())
