"""
Markdown → Telegram-HTML rendering for digest messages.

The LLM synthesis emits markdown (`# / ## / ###` headers, `**bold**`, `- ` /
`1.` lists). Telegram has NO header markup and renders only a small HTML subset
(<b> <i> <u> <s> <a> <code> <pre>). This module converts our markdown to that
subset and ships it with parse_mode=HTML, with a plain-text fallback if Telegram
still rejects the entities.

Why HTML, not MarkdownV2: HTML escapes only `< > &`, so the digest's PII refs
`[Имя, 2026-05-29]` and ordinary Russian punctuation (`.`, `-`, `(`, `!`) pass
through untouched. MarkdownV2 would force escaping `[ ] . - ( )` everywhere —
far more error-prone on long Russian prose → frequent 400 "can't parse entities".

Lists are left as-is on purpose: Telegram renders neither HTML lists nor markdown
bullets as real lists, so `- пункт` / `1. пункт` stay readable text either way.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Headers: 1-3 leading '#'+space at line start → bold line. Telegram has no
# header type, so all levels collapse to <b>. Emoji/text after the hashes stay.
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
# **bold** → <b>bold</b>. Non-greedy, no newline inside, must be non-empty.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def _escape_html(text: str) -> str:
    """Escape the 3 chars Telegram-HTML treats as special. Order matters: & first."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_to_telegram_html(text: str) -> str:
    """Convert digest markdown to the Telegram-HTML subset.

    Pipeline (order is load-bearing):
      1. escape < > &  — so any literal angle brackets in the text are inert
         BEFORE we insert our own <b> tags (escaping later would mangle them).
      2. headers `#..###` → <b>…</b> on that line.
      3. `**bold**`       → <b>bold</b>.

    PII refs like [Имя, 2026-05-29] contain none of < > & and no `**`, so they
    pass through verbatim — brackets stay literal, the ref renders as plain text.
    """
    out = _escape_html(text)
    out = _HEADER_RE.sub(lambda m: f"<b>{m.group(2).strip()}</b>", out)
    out = _BOLD_RE.sub(lambda m: f"<b>{m.group(1)}</b>", out)
    return out


async def send_formatted_dm(bot, chat_id: int, text: str) -> None:
    """DM `text` to `chat_id`, rendering its markdown as Telegram-HTML.

    Reliability contract: if Telegram rejects the HTML entities (BadRequest
    "can't parse entities" — e.g. an unbalanced tag the converter didn't catch),
    we RESEND the ORIGINAL markdown as plain text (no parse_mode). Better an
    ugly message than none — the caller must never be left without a reply.

    Only entity-parse BadRequests trigger the fallback; other errors (Forbidden,
    chat-not-found, message-too-long) propagate so the caller handles them as
    before (e.g. the /start hint on Forbidden).

    `bot` is a telegram.Bot (or anything with an async send_message). Sync
    callers wrap this in asyncio.run themselves.
    """
    from telegram.constants import ParseMode
    from telegram.error import BadRequest

    html = markdown_to_telegram_html(text)
    try:
        await bot.send_message(chat_id=chat_id, text=html, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "can't parse entities" not in str(e).lower():
            raise  # not a formatting problem — let the caller deal with it
        logger.warning("HTML parse failed (%s); resending as plain text", e)
        await bot.send_message(chat_id=chat_id, text=text)
