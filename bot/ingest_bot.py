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
from core.brain.synthesis import TOPIC_HINTS, MAX_FRAGMENTS_WITHOUT_SELECTION
from core.store.fragments_db import (
    get_topics_with_counts, count_embedded_fragments_for_period)
from delivery.cli import (
    build_digest, count_fragments, parse_date_range, build_topics_digest)
from delivery.markup import send_formatted_dm

logger = logging.getLogger(__name__)

TG_MSG_LIMIT = 4096  # Telegram hard cap per message

DEFAULT_TOPICS_LIMIT = 10  # /topics: top-N themes when no explicit limit given


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
        # only known topics (TOPIC_HINTS) — stray/foreign mappings don't surface
        topics = get_topics_with_counts(only=set(TOPIC_HINTS))
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

    from_s, till_s = args[1], args[2]
    logger.info("summary user=%s topic=%s %s..%s", user_id, topic, since, until)

    # 4. ACK first (cheap count, no OpenAI) so the caller sees it picked up the
    #    request before the slow synthesis. 0 fragments -> stop here, no spend.
    try:
        found = await asyncio.to_thread(count_fragments, topic, since, until)
    except Exception:
        logger.exception("summary count FAILED user=%s topic=%s", user_id, topic)
        await update.message.reply_text("Не удалось обработать запрос — ошибка на сервере.")
        return

    if found == 0:
        await update.message.reply_text(
            f"Топик: {topic} | Период: {from_s}..{till_s}\nЗа этот период сообщений нет.")
        logger.info("summary EMPTY user=%s topic=%s", user_id, topic)
        return

    await update.message.reply_text(
        f"Топик: {topic} | Период: {from_s}..{till_s}\n"
        f"Найдено {found} сообщений, передаю в модель максимум "
        f"{MAX_FRAGMENTS_WITHOUT_SELECTION}. Собираю саммари…")

    # 5. synthesize off the event loop.
    try:
        result = await asyncio.to_thread(build_digest, topic, since, until)
    except Exception:
        logger.exception("summary synth FAILED user=%s topic=%s", user_id, topic)
        await update.message.reply_text("Не удалось собрать саммари — ошибка на сервере.")
        return

    if result is None:  # race: emptied between count and synth — no spend happened
        await update.message.reply_text("За этот период по топику нет сообщений.")
        return

    # 6. deliver the digest as its OWN message to the CALLER's DM. Kept clean
    #    (no stats line) so it can later be forwarded to a dedicated topic as-is.
    #    Always DM the caller, never the group.
    digest = result['text'][:TG_MSG_LIMIT]
    try:
        await send_formatted_dm(context.bot, user_id, digest)
        logger.info("summary SENT user=%s topic=%s found=%d used=%d len=%d",
                    user_id, topic, found, result['used'], len(digest))
    except Forbidden:
        await update.message.reply_text(
            "Напиши мне в личку и нажми /start, чтобы я мог прислать саммари.")
        logger.info("summary FORBIDDEN (no DM) user=%s", user_id)


class TopicsArgError(ValueError):
    """Raised for any bad /topics input — message is the user-facing reply."""


def validate_topics_args(args: list[str]) -> tuple[str, object, object, int]:
    """Validate `/topics <topic> <from> <till> [limit]` -> (topic, since, until, limit).

    Raises TopicsArgError with a friendly Russian message on any problem
    (wrong arg count, unknown topic, 'all', bad date, from>till, bad limit).
    Pure — no DB / no OpenAI / no Telegram, so it's unit-testable. The
    0-fragments case is handled later (after the DB count) so we never spend
    OpenAI on an empty period.
    """
    if len(args) not in (3, 4):
        raise TopicsArgError(
            "Формат: /topics <topic> <YYYY-MM-DD> <YYYY-MM-DD> [limit]\n"
            "Пример: /topics boltalka 2026-05-01 2026-05-31 10")
    topic, from_s, till_s = args[0], args[1], args[2]
    if topic == "all":
        raise TopicsArgError("/topics работает с ОДНИМ топиком, не all.")
    if topic not in TOPIC_HINTS:
        known = ", ".join(sorted(TOPIC_HINTS))
        raise TopicsArgError(f"Неизвестный топик «{topic}».\nДоступные: {known}")
    try:
        since, until = parse_date_range(from_s, till_s)
    except ValueError:
        raise TopicsArgError(
            "Неверные даты. Формат YYYY-MM-DD, и from ≤ till.\n"
            "Пример: 2026-05-01 2026-05-31")
    if len(args) == 4:
        try:
            limit = int(args[3])
        except ValueError:
            raise TopicsArgError("limit должен быть числом. Пример: /topics boltalka 2026-05-01 2026-05-31 10")
        if limit <= 0:
            raise TopicsArgError("limit должен быть больше нуля.")
    else:
        limit = DEFAULT_TOPICS_LIMIT
    return topic, since, until, limit


def _topics_help() -> str:
    """Format help + the list of topics that actually have fragments.

    NOTE: the counts here follow get_topics_with_counts' filter (min_chars=150)
    and will NOT match the /topics ack count (count_embedded_fragments_for_period,
    a different filter). That's fine: help is a rough 'which topics exist' guide,
    the ack is the exact per-period count. Don't try to sync them.
    """
    try:
        # only known topics (TOPIC_HINTS) — stray/foreign mappings don't surface
        topics = get_topics_with_counts(only=set(TOPIC_HINTS))
    except Exception:
        logger.exception("topics: failed to list topics")
        topics = []
    lines = [
        "Формат: /topics <topic> <YYYY-MM-DD> <YYYY-MM-DD> [limit]",
        "Пример: /topics boltalka 2026-05-01 2026-05-31 10",
    ]
    if topics:
        lines.append("\nДоступные топики (с числом сообщений):")
        lines += [f"• {t} ({c})" for t, c in topics]
    return "\n".join(lines)


async def on_topics(update, context):
    """/topics <topic> <from> <till> [limit] — hot-topics digest, DM the caller.

    Whitelist (fail-closed) -> validate args -> cheap COUNT ack -> (if any)
    build_topics_digest -> send to the CALLER's private chat. OpenAI is only
    touched inside build_topics (theme names), so denied users / bad input /
    empty periods cost nothing.
    """
    user = update.effective_user
    user_id = user.id if user else None

    # 1. whitelist (fail-closed: empty ALLOWED denies everyone)
    if user_id not in ALLOWED:
        await update.message.reply_text("Команда доступна только администраторам.")
        logger.info("topics DENIED user=%s", user_id)
        return

    # 2. no args -> help + topic list
    args = context.args
    if not args:
        await update.message.reply_text(_topics_help())
        return

    # 3. validate args (topic known, not 'all', dates ok, limit ok)
    try:
        topic, since, until, limit = validate_topics_args(args)
    except TopicsArgError as e:
        await update.message.reply_text(str(e))
        return

    from_s, till_s = args[1], args[2]
    logger.info("topics user=%s topic=%s %s..%s limit=%d",
                user_id, topic, since, until, limit)

    # 4. ACK first (cheap count, no OpenAI) so the caller sees it picked up the
    #    request before the slow clustering. 0 fragments -> stop here, no spend.
    try:
        found = await asyncio.to_thread(
            count_embedded_fragments_for_period, topic, since, until)
    except Exception:
        logger.exception("topics count FAILED user=%s topic=%s", user_id, topic)
        await update.message.reply_text("Не удалось обработать запрос — ошибка на сервере.")
        return

    if found == 0:
        await update.message.reply_text(
            f"Топик: {topic} | Период: {from_s}..{till_s}\nЗа этот период сообщений нет.")
        logger.info("topics EMPTY user=%s topic=%s", user_id, topic)
        return

    await update.message.reply_text(
        f"Топик: {topic} | Период: {from_s}..{till_s}\n"
        f"Найдено {found} сообщений, собираю горячие темы…")

    # 5. clustering + LLM theme names off the event loop. No ValueError here:
    #    topic is already validated (not 'all').
    try:
        result = await asyncio.to_thread(build_topics_digest, topic, since, until, limit)
    except Exception:
        logger.exception("topics build FAILED user=%s topic=%s", user_id, topic)
        await update.message.reply_text("Не удалось собрать темы — ошибка на сервере.")
        return

    if result is None:  # race: emptied between count and build — no spend happened
        await update.message.reply_text("За этот период по топику нет сообщений.")
        return

    # 6. deliver the digest as its OWN message to the CALLER's DM. Kept clean
    #    (no stats line) so it can later be forwarded to a dedicated topic as-is.
    #    Always DM the caller, never the group.
    digest = result['text'][:TG_MSG_LIMIT]
    try:
        await send_formatted_dm(context.bot, user_id, digest)
        logger.info("topics SENT user=%s topic=%s found=%d len=%d",
                    user_id, topic, found, len(digest))
    except Forbidden:
        await update.message.reply_text(
            "Напиши мне в личку и нажми /start, чтобы я мог прислать дайджест.")
        logger.info("topics FORBIDDEN (no DM) user=%s", user_id)


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
    app.add_handler(CommandHandler("topics", on_topics))
    # content messages; service updates (joins/leaves/title/pin) are filtered out
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
