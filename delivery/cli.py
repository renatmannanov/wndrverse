"""
Delivery CLI — the MVP entry point.

    python -m delivery digest --topic offerings --period 1w [--channel stdout]

Flow: get_fragments_for_digest → synthesize → humanize [#id] refs locally → send.

PII: names are substituted here, locally from the DB. They are NOT sent to OpenAI
(synthesis only ever sees [#id] + text).
"""

import os
import re
import sys
import logging
from datetime import datetime, timedelta

from core.store.fragments_db import get_fragments_for_digest, get_fragments_by_ids
from core.brain.synthesis import synthesize_and_save, TOPIC_HINTS
from delivery import channels

logger = logging.getLogger(__name__)

# [#207] / [207] / #207 / (#207) — tolerant of how the LLM wraps the id.
_REF_RE = re.compile(r"\[?#?(\d+)\]?")


def parse_period(period: str) -> datetime | None:
    """Translate a period string to a `since` datetime.

    'all' → None (whole corpus). Suffixes: h=hours, d=days, w=weeks, m=months(30d).
    Unknown suffix → raises (no silent fallback).
    """
    period = period.strip().lower()
    if period == "all":
        return None
    if len(period) < 2:
        raise ValueError(f"bad period: {period!r}")
    try:
        n = int(period[:-1])
    except ValueError:
        raise ValueError(f"bad period number: {period!r}")
    unit = period[-1]
    if unit == "h":
        delta = timedelta(hours=n)
    elif unit == "d":
        delta = timedelta(days=n)
    elif unit == "w":
        delta = timedelta(weeks=n)
    elif unit == "m":
        delta = timedelta(days=30 * n)
    else:
        raise ValueError(f"unknown period suffix {unit!r} in {period!r} (use h/d/w/m/all)")
    return datetime.utcnow() - delta


def parse_date_range(from_s: str, till_s: str) -> tuple[datetime, datetime]:
    """Translate two YYYY-MM-DD strings into (since, until) for the digest query.

    The range is INCLUSIVE on both ends by day:
      since = date_from at 00:00 (UTC)
      until = date_till + 1 day at 00:00 (UTC)  — EXCLUSIVE upper bound
    so a fragment at 23:59 on date_till is included (created_at < until).
    Dates are treated as UTC midnight (MVP; created_at in the DB is UTC).

    Raises ValueError on a malformed date or if from > till — the caller turns
    this into a friendly reply and never spends OpenAI on it.
    """
    try:
        since = datetime.strptime(from_s, "%Y-%m-%d")
        till = datetime.strptime(till_s, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"bad date (use YYYY-MM-DD): {from_s!r} / {till_s!r}")
    if since > till:
        raise ValueError(f"from > till: {from_s} > {till_s}")
    until = till + timedelta(days=1)
    return since, until


def humanize_refs(content: str, fragment_ids: list[int]) -> str:
    """Replace [#id] refs in the digest with [author_name, date], from the local DB.

    Author/date come from our DB, never from the LLM. Unknown ids and unmatched
    formats are left as-is (the digest stays readable, just without a name).
    """
    frags = {f['id']: f for f in get_fragments_by_ids(fragment_ids)}

    def repl(m: re.Match) -> str:
        fid = int(m.group(1))
        f = frags.get(fid)
        if not f:
            return m.group(0)  # not one of ours — leave untouched
        name = f.get('author_name') or "аноним"
        if f.get('sender_id') is None:
            name = "аноним"
        date = (f.get('created_at') or "")[:10]
        return f"[{name}, {date}]" if date else f"[{name}]"

    return _REF_RE.sub(repl, content)


def build_digest(
    topic_arg: str,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict | None:
    """Core: select → synthesize → humanize [#id] refs locally → return result.

    The single shared synthesis path used by BOTH the scheduler (fixed period)
    and the bot's /summary command (exact date range). No sending — the caller
    picks the channel.

    Returns {'text': str, 'found': int, 'used': int} where `found` is how many
    fragments the period had and `used` is how many were fed to the model (all,
    unless Pass-1 trimmed a large period). Returns None if there were 0 fragments
    (so the caller skips OpenAI spend on an empty period — synthesis never runs).

    until is the UPPER bound EXCLUSIVE (see get_fragments_for_digest).
    """
    topic = None if topic_arg == "all" else topic_arg
    topic_type = topic_arg if topic_arg in TOPIC_HINTS else None

    fragments = get_fragments_for_digest(topic=topic, since=since, until=until)
    logger.info("digest topic=%s since=%s until=%s → %d fragments",
                topic_arg, since, until, len(fragments))
    if not fragments:
        return None  # no spend on an empty period

    result = synthesize_and_save(topic_arg, fragments, topic_type=topic_type)
    text = humanize_refs(result['content'], result['fragment_ids'])
    return {
        'text': text,
        'found': result.get('found', len(fragments)),
        'used': len(result['fragment_ids']),
    }


def _run_digest(topic_arg: str, period: str, channel: str) -> int:
    since = parse_period(period)
    result = build_digest(topic_arg, since=since)
    if result is None:
        logger.info("digest topic=%s period=%s → 0 fragments, nothing to send",
                    topic_arg, period)
        return 0
    text = result['text']
    channels.send(text, channel=channel)
    return 0


def _main(argv: list[str]) -> int:
    import argparse

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(prog="delivery", description="Community brain delivery")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("digest", help="Generate and deliver a digest")
    d.add_argument("--topic", required=True, help="topic name (offerings/harvest/...) or 'all'")
    d.add_argument("--period", default="all", help="1w / 3d / 12h / 1m / all")
    d.add_argument("--channel", default="stdout", help="stdout (telegram_* are future)")
    args = parser.parse_args(argv)

    if args.command == "digest":
        return _run_digest(args.topic, args.period, args.channel)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
