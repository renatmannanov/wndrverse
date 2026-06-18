"""Unit tests for delivery.topics_render — t.me links, plural, render. No DB/LLM."""

from delivery.topics_render import tg_link, plural_msgs, render_topics, EMOJI


def test_tg_link_ok():
    assert tg_link(-1002924475859, 'tg_-1002924475859_9307') == \
        'https://t.me/c/2924475859/9307'


def test_tg_link_bad():
    assert tg_link(-1002924475859, 'bad') == ''                  # no underscore tail
    # legacy 'wndr_…' rows carry a NULL/non-(-100) channel_id, so the channel_id
    # guard is what drops them (not the external_id parse). With a None channel_id:
    assert tg_link(None, 'wndr_chatname_415') == ''
    # channel_id without -100 prefix → '' even if the tail is a digit
    assert tg_link(12345, 'tg_12345_9307') == ''
    # non-digit tail → ''
    assert tg_link(-1002924475859, 'tg_-1002924475859_abc') == ''


def test_plural_msgs():
    assert plural_msgs(1) == 'сообщение'
    assert plural_msgs(3) == 'сообщения'
    assert plural_msgs(5) == 'сообщений'
    assert plural_msgs(12) == 'сообщений'
    assert plural_msgs(22) == 'сообщения'
    assert plural_msgs(11) == 'сообщений'


def test_render_topics():
    topics = [
        {'name': 'SaaS-апокалипсис', 'msgs': 22,
         'anchor_channel_id': -1002924475859, 'anchor_external_id': 'tg_-1002924475859_9307'},
        {'name': 'Будущее SaaS', 'msgs': 14,
         'anchor_channel_id': -1002924475859, 'anchor_external_id': 'tg_-1002924475859_9308'},
    ]
    out = render_topics('📅 Болталка · 2026-05-09 — 2026-06-09', topics)
    assert 'https://t.me/c/2924475859/9307' in out
    assert 'https://t.me/c/2924475859/9308' in out
    assert '(22 сообщения)' in out
    assert '(14 сообщений)' in out
    # emoji from palette in order
    assert f"{EMOJI[0]} SaaS-апокалипсис" in out
    assert f"{EMOJI[1]} Будущее SaaS" in out


def test_render_skips_empty_link():
    topics = [{'name': 'тема', 'msgs': 3,
               'anchor_channel_id': 12345, 'anchor_external_id': 'bad'}]
    out = render_topics('hdr', topics)
    assert 'https://t.me' not in out   # no valid link → no link line
    assert '(3 сообщения)' in out


def test_render_intrigue_between_name_and_link():
    topics = [{'name': 'SaaS-апокалипсис', 'intrigue': 'Кто-то ушёл, а спор остался.',
               'msgs': 22, 'anchor_channel_id': -1002924475859,
               'anchor_external_id': 'tg_-1002924475859_9307'}]
    out = render_topics('hdr', topics)
    lines = out.splitlines()
    name_i = next(i for i, l in enumerate(lines) if 'SaaS-апокалипсис' in l)
    intrigue_i = next(i for i, l in enumerate(lines) if 'Кто-то ушёл' in l)
    link_i = next(i for i, l in enumerate(lines) if 'https://t.me' in l)
    assert name_i < intrigue_i < link_i   # hook sits between name and link


def test_render_no_intrigue_key_old_format():
    """A topic dict WITHOUT the 'intrigue' key (old fixtures) must not crash and
    renders the old name+link format (render reads it via .get)."""
    topics = [{'name': 'тема', 'msgs': 5,
               'anchor_channel_id': -1002924475859,
               'anchor_external_id': 'tg_-1002924475859_9307'}]
    out = render_topics('hdr', topics)
    assert 'тема' in out and 'https://t.me/c/2924475859/9307' in out


def test_render_blank_line_between_topics():
    """Topics are separated by a blank line; no trailing blank after the last."""
    topics = [
        {'name': 'A', 'intrigue': 'крючок A', 'msgs': 5,
         'anchor_channel_id': -1002924475859, 'anchor_external_id': 'tg_-1002924475859_9307'},
        {'name': 'B', 'intrigue': 'крючок B', 'msgs': 3,
         'anchor_channel_id': -1002924475859, 'anchor_external_id': 'tg_-1002924475859_9308'},
    ]
    out = render_topics('hdr', topics)
    # blank line between the two topic blocks: link of A, empty, emoji of B
    assert '/9307\n\n' in out
    # no trailing blank line after the last topic
    assert not out.endswith('\n')


def test_render_empty_intrigue_omits_line():
    topics = [{'name': 'тема', 'intrigue': '', 'msgs': 5,
               'anchor_channel_id': -1002924475859,
               'anchor_external_id': 'tg_-1002924475859_9307'}]
    out = render_topics('hdr', topics)
    # exactly header(+blank) + name line + link line; no extra hook line
    assert len([l for l in out.splitlines() if l.strip()]) == 3
