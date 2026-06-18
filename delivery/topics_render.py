"""
Hot-topics rendering: TopicCluster[] → target text with t.me links.

Knows NOTHING about clustering/LLM — it only formats the structure built by
core.brain.topics. The emoji palette lives here (the render assigns emoji by
position; the LLM never invents emoji).

TopicCluster contract (built by brain.topics.build_topics):
    {
      'name': str,                # topic name (LLM, in Russian)
      'intrigue': str,            # one-line hook (LLM); may be "" / absent → skipped
      'msgs': int,                # number of messages in the cluster
      'anchor_channel_id': int,   # -100… form (from the anchor message)
      'anchor_external_id': str,  # 'tg_-100…_<msg_id>' (from the anchor message)
    }
There is NO 'emoji' field — the render assigns it by position. 'intrigue' is read
via .get — an empty or missing key just omits the hook line (old format).
"""

# Fixed palette: topic emoji = EMOJI[i % len(EMOJI)], i = index in the sorted list.
EMOJI = ['📈', '🔮', '📊', '🔄', '💹', '💼', '🚀', '📉', '🔍', '📌', '💡', '🔥', '⚡', '🌱', '🎯']


def tg_link(channel_id: int, external_id: str) -> str:
    """https://t.me/c/<internal>/<msg_id>.

    internal = channel_id without the -100 prefix: str(channel_id) starts with
      '-100', drop 4 chars → '2924475859'. (-1002924475859 → 2924475859.)
    msg_id = external_id.rsplit('_', 1)[1] — from the END once: the channel_id
      inside external_id ITSELF contains '_' and '-', a plain split would break.
    If external_id doesn't parse / channel_id doesn't start with '-100' → return ''
      (link is skipped, the topic stays link-less, no crash).
    """
    cid = str(channel_id)
    if not cid.startswith('-100'):
        return ''
    internal = cid[4:]
    if not internal:
        return ''
    try:
        msg_id = external_id.rsplit('_', 1)[1]
    except (AttributeError, IndexError):
        return ''
    if not msg_id.isdigit():
        return ''
    return f"https://t.me/c/{internal}/{msg_id}"


def plural_msgs(n: int) -> str:
    """Russian plural of 'сообщение': 1→'сообщение', 2-4→'сообщения', else 'сообщений'.

    11-14 → 'сообщений' regardless of the last digit (n % 100 in 11..14).
    """
    if 11 <= n % 100 <= 14:
        return 'сообщений'
    last = n % 10
    if last == 1:
        return 'сообщение'
    if 2 <= last <= 4:
        return 'сообщения'
    return 'сообщений'


def render_topics(header: str, topics: list[dict]) -> str:
    """header + topic lines. Target format:

    📅 Болталка · 2026-05-09 — 2026-06-09

    📈 <name> (22 сообщения)
       <intrigue — one-line hook, only if non-empty>
       https://t.me/c/2924475859/9307
    🔮 <name> (14 сообщений)
       https://t.me/c/2924475859/9308

    topics are already sorted by hotness (step 5). Emoji from the palette by topic
    index. The intrigue line sits BETWEEN the name and the link, printed only when
    non-empty (empty/absent → old format). An empty link → the link line is NOT
    printed (topic stays link-less).
    """
    lines = [header, ""]
    for i, t in enumerate(topics):
        emoji = EMOJI[i % len(EMOJI)]
        n = t['msgs']
        lines.append(f"{emoji} {t['name']} ({n} {plural_msgs(n)})")
        intrigue = (t.get('intrigue') or "").strip()
        if intrigue:
            lines.append(f"   {intrigue}")
        link = tg_link(t['anchor_channel_id'], t['anchor_external_id'])
        if link:
            lines.append(f"   {link}")
    return "\n".join(lines)
