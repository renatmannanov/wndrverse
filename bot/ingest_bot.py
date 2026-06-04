"""Realtime ingest bot: python-telegram-bot (polling) -> core ingest().

Long-lived process. Each new message from a mapped chat becomes one Fragment
and is written to the DB via the same funnel as the file loader.

Run (module form only — `python bot/ingest_bot.py` breaks `core.*` imports):
    python -m bot.ingest_bot
"""

import asyncio
import logging
import os

from telegram.error import Forbidden
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from core.ingest.loaders import ingest
from core.ingest.bot_adapter import bot_message_to_fragment
from core.ingest.topic_map import resolve_topic
from core.brain.synthesis import TOPIC_HINTS
from core.store.fragments_db import get_topics_with_counts
from delivery.cli import build_digest, parse_date_range

logger = logging.getLogger(__name__)

TG_MSG_LIMIT = 4096  # Telegram hard cap per message


def parse_allowed(raw: str | None) -> set[int]:
    """Parse WNDR_SUMMARY_ALLOWED (CSV of user_ids) into a set[int].

    Empty / unset / all-garbage -> empty set => nobody is allowed (fail-closed).
    """
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            logger.warning("WNDR_SUMMARY_ALLOWED: ignoring non-int %r", part)
    return out


# Validated at bot startup (main); module-level so the handler closes over it.
ALLOWED: set[int] = set()


class SummaryArgError(ValueError):
    """Raised for any bad /summary input — message is the user-facing reply."""


def validate_summary_args(args: list[str]) -> tuple[str, object, object]:
    """Validate `/summary <topic> <from> <till>` args -> (topic, since, until).

    Raises SummaryArgError with a friendly Russian message on any problem
    (wrong arg count, unknown topic, bad date, from>till). Pure — no DB / no
    OpenAI / no Telegram, so it's unit-testable. The 0-fragments case is handled
    later (after the DB query) so we never spend OpenAI on an empty period.
    """
    if len(args) != 3:
        raise SummaryArgError(
            "Формат: /summary <topic> <YYYY-MM-DD> <YYYY-MM-DD>\n"
            "Пример: /summary questions_to_women 2026-05-01 2026-05-31")
    topic, from_s, till_s = args
    if topic not in TOPIC_HINTS:
        known = ", ".join(sorted(TOPIC_HINTS))
        raise SummaryArgError(f"Неизвестный топик «{topic}».\nДоступные: {known}")
    try:
        since, until = parse_date_range(from_s, till_s)
    except ValueError:
        raise SummaryArgError(
            "Неверные даты. Формат YYYY-MM-DD, и from ≤ till.\n"
            "Пример: 2026-05-01 2026-05-31")
    return topic, since, until


def _summary_help() -> str:
    """Format help + the list of topics that actually have fragments."""
    try:
        topics = get_topics_with_counts()
    except Exception:
        logger.exception("summary: failed to list topics")
        topics = []
    lines = [
        "Формат: /summary <topic> <YYYY-MM-DD> <YYYY-MM-DD>",
        "Пример: /summary questions_to_women 2026-05-01 2026-05-31",
    ]
    if topics:
        lines.append("\nДоступные топики (с числом сообщений):")
        lines += [f"• {t} ({c})" for t, c in topics]
    return "\n".join(lines)


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


async def on_summary(update, context):
    """/summary <topic> <from> <till> — synthesize a range digest, DM the caller.

    Whitelist (fail-closed) -> validate args -> select fragments -> (if any)
    synthesize+humanize -> send to the CALLER's private chat. OpenAI is only ever
    touched after a non-empty selection, so denied users / bad input / empty
    periods cost nothing.
    """
    user = update.effective_user
    user_id = user.id if user else None

    # 1. whitelist (fail-closed: empty ALLOWED denies everyone)
    if user_id not in ALLOWED:
        await update.message.reply_text("Команда доступна только администраторам.")
        logger.info("summary DENIED user=%s", user_id)
        return

    # 2. no args -> help + topic list
    args = context.args
    if not args:
        await update.message.reply_text(_summary_help())
        return

    # 3. validate args (topic known, dates ok, from<=till)
    try:
        topic, since, until = validate_summary_args(args)
    except SummaryArgError as e:
        await update.message.reply_text(str(e))
        return

    logger.info("summary user=%s topic=%s %s..%s", user_id, topic, since, until)

    # 4. select + synthesize off the event loop. build_digest returns None for
    #    an empty period -> reply without spending OpenAI.
    try:
        text = await asyncio.to_thread(build_digest, topic, since, until)
    except Exception:
        logger.exception("summary synth FAILED user=%s topic=%s", user_id, topic)
        await update.message.reply_text("Не удалось собрать саммари — ошибка на сервере.")
        return

    if text is None:
        await update.message.reply_text("За этот период по топику нет сообщений.")
        logger.info("summary EMPTY user=%s topic=%s", user_id, topic)
        return

    # 5. deliver to the CALLER's DM (not the group, not the fixed DM_USER_ID).
    try:
        await context.bot.send_message(chat_id=user_id, text=text[:TG_MSG_LIMIT])
        logger.info("summary SENT user=%s topic=%s len=%d", user_id, topic, len(text))
    except Forbidden:
        await update.message.reply_text(
            "Напиши мне в личку и нажми /start, чтобы я мог прислать саммари.")
        logger.info("summary FORBIDDEN (no DM) user=%s", user_id)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from dotenv import load_dotenv
        load_dotenv()  # BOT_TOKEN_INGEST / WNDR_TOPIC_MAP / DATABASE_URL from .env
    except ImportError:
        pass

    global ALLOWED
    ALLOWED = parse_allowed(os.environ.get("WNDR_SUMMARY_ALLOWED"))
    logger.info("summary whitelist: %d user(s)", len(ALLOWED))

    token = os.environ["BOT_TOKEN_INGEST"]
    app = Application.builder().token(token).build()
    # /summary must be registered BEFORE the catch-all MessageHandler so the
    # command isn't also treated as ingest content. (PTB dispatches the first
    # matching handler in group 0.)
    app.add_handler(CommandHandler("summary", on_summary))
    # content messages; service updates (joins/leaves/title/pin) are filtered out
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
