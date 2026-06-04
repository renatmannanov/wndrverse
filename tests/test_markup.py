"""Unit tests for delivery.markup — markdown→Telegram-HTML + send-with-fallback.

Telegram-free: send_formatted_dm is driven against fake bots (asyncio.run),
no real network. Covers:
  - header (# / ## / ###) → <b>…</b>
  - **bold** → <b>…</b>
  - HTML escaping of < > & (so literal angle brackets don't break entities)
  - PII refs [Имя, 2026-05-29] pass through verbatim (the core risk)
  - send: parse_mode=HTML on the happy path
  - send: 400 "can't parse entities" → plain-text fallback (original markdown)
  - send: other BadRequest / Forbidden propagate (no silent swallow)
"""

import asyncio

import pytest

from delivery.markup import markdown_to_telegram_html, send_formatted_dm


# --- markdown_to_telegram_html ---------------------------------------------

def test_headers_become_bold():
    assert markdown_to_telegram_html("# Заголовок") == "<b>Заголовок</b>"
    assert markdown_to_telegram_html("## 📌 ТЕМЫ") == "<b>📌 ТЕМЫ</b>"
    assert markdown_to_telegram_html("### Под") == "<b>Под</b>"


def test_header_only_at_line_start():
    # a '#' mid-line (e.g. a ref like #207) must NOT become a header
    assert markdown_to_telegram_html("см #207 тут") == "см #207 тут"


def test_bold_converts():
    assert markdown_to_telegram_html("**Финансы**: рост") == "<b>Финансы</b>: рост"


def test_bold_inside_numbered_list_line():
    src = "1. **Тема**: описание"
    assert markdown_to_telegram_html(src) == "1. <b>Тема</b>: описание"


def test_html_special_chars_escaped():
    assert markdown_to_telegram_html("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_escape_runs_before_bold_insert():
    # the <b> we insert must survive — literal '<' in text is escaped, ours is not
    out = markdown_to_telegram_html("**x < y**")
    assert out == "<b>x &lt; y</b>"


def test_pii_ref_passes_through_untouched():
    # THE core guarantee: brackets/comma/date in a PII ref stay literal text
    src = "Важно [Имя, 2026-05-29] и ещё [аноним]"
    assert markdown_to_telegram_html(src) == src


def test_realistic_digest_block():
    src = (
        "# Дайджест топика «Questions to Women»\n"
        "## 📌 ГЛАВНЫЕ ТЕМЫ периода\n"
        "1. **Финансовая динамика**: обсуждали бюджет [Аня, 2026-05-29]\n"
        "- запрос на менторство [Лена, 2026-05-30]"
    )
    out = markdown_to_telegram_html(src)
    assert "<b>Дайджест топика «Questions to Women»</b>" in out
    assert "<b>📌 ГЛАВНЫЕ ТЕМЫ периода</b>" in out
    assert "<b>Финансовая динамика</b>" in out
    # list markers and PII refs untouched
    assert "1. <b>Финансовая динамика</b>" in out
    assert "- запрос на менторство [Лена, 2026-05-30]" in out
    assert "[Аня, 2026-05-29]" in out


# --- send_formatted_dm: happy path + fallback ------------------------------

class _Bot:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.calls.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})


def test_send_uses_html_parse_mode():
    from telegram.constants import ParseMode

    bot = _Bot()
    asyncio.run(send_formatted_dm(bot, 42, "**bold**"))
    assert len(bot.calls) == 1
    c = bot.calls[0]
    assert c["chat_id"] == 42
    assert c["parse_mode"] == ParseMode.HTML
    assert c["text"] == "<b>bold</b>"


class _ParseFailBot:
    """First send (HTML) raises a 'can't parse entities' BadRequest; record both."""

    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text, parse_mode=None):
        from telegram.error import BadRequest

        self.calls.append({"text": text, "parse_mode": parse_mode})
        if parse_mode is not None:
            raise BadRequest("Can't parse entities: unexpected end tag")


def test_send_falls_back_to_plain_on_parse_error():
    bot = _ParseFailBot()
    asyncio.run(send_formatted_dm(bot, 1, "**x**"))
    assert len(bot.calls) == 2
    # 1st: HTML attempt; 2nd: plain text = ORIGINAL markdown, no parse_mode
    assert bot.calls[0]["parse_mode"] is not None
    assert bot.calls[1]["parse_mode"] is None
    assert bot.calls[1]["text"] == "**x**"


def test_send_propagates_non_entity_badrequest():
    from telegram.error import BadRequest

    class _OtherBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            raise BadRequest("chat not found")

    with pytest.raises(BadRequest):
        asyncio.run(send_formatted_dm(_OtherBot(), 1, "x"))


def test_send_propagates_forbidden():
    from telegram.error import Forbidden

    class _ForbidBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            raise Forbidden("blocked")

    with pytest.raises(Forbidden):
        asyncio.run(send_formatted_dm(_ForbidBot(), 1, "x"))
