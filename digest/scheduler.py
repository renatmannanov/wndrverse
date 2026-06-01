"""Digest scheduler — a long-lived stdlib sleep-loop (no APScheduler/cron).

Once a day at WNDR_DIGEST_AT in zone WNDR_DIGEST_TZ it synthesizes a digest per
WNDR topic and DMs it to the user, reusing delivery.cli._run_digest (the same
synth+humanize+send path the CLI uses). Schedule is pinned to a NAMED zone so a
future move to a UTC VPS does not shift the send moment.

Run (module form only — `python digest/scheduler.py` breaks `delivery.*` imports):
    python -m digest.scheduler          # loop forever on schedule
    python -m digest.scheduler --now    # run once immediately and exit

Config (all ENV, with defaults):
    WNDR_DIGEST_TZ      schedule timezone           (default Asia/Almaty)
    WNDR_DIGEST_AT      run time HH:MM              (default 09:00)
    WNDR_DIGEST_PERIOD  message lookback window     (default 1d)
    WNDR_DIGEST_TOPICS  comma-separated topic list  (default questions_to_women,questions_to_men)
    WNDR_DIGEST_DM_USER_ID  DM recipient (used by delivery.channels, step 2)

MVP note: no missed-run recovery. If the process is down past the target time,
_seconds_until_next schedules the next run for tomorrow; the missed digest is NOT
backfilled (no persistent "last run" state) — deliberate for the sleep-loop MVP.
"""

import argparse
import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Module-level imports so tests can monkeypatch scheduler.<name> uniformly.
from delivery.cli import _run_digest, parse_period
from core.store.fragments_db import get_fragments_for_digest

logger = logging.getLogger(__name__)


def _seconds_until_next(at_hhmm: str, tz: ZoneInfo) -> float:
    """Seconds until the next occurrence of at_hhmm (HH:MM) in zone tz."""
    hh, mm = map(int, at_hhmm.split(":"))
    now = datetime.now(tz)
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_once(topics: list[str], period: str) -> None:
    """One pass: per topic, synthesize a digest and DM it.

    Guard (V1): a topic with 0 fragments for the period is skipped WITHOUT synthesis
    — no OpenAI spend on emptiness, no useless "not enough data" DM. The re-query of
    fragments here is one cheap SELECT (not OpenAI); the real synth re-queries inside
    _run_digest. We deliberately don't optimize that away (would mean rewriting core).
    """
    since = parse_period(period)
    for topic in topics:
        try:
            frags = get_fragments_for_digest(topic=topic, since=since)
            if not frags:
                logger.info("skip topic=%s — 0 fragments for period=%s", topic, period)
                continue
            _run_digest(topic, period, channel="telegram_dm")
            logger.info("digest sent: topic=%s period=%s (%d frags)", topic, period, len(frags))
        except Exception:
            logger.exception("digest FAILED topic=%s (continuing)", topic)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(prog="digest.scheduler")
    parser.add_argument("--now", action="store_true", help="run once immediately and exit")
    args = parser.parse_args()

    tz = ZoneInfo(os.getenv("WNDR_DIGEST_TZ", "Asia/Almaty"))
    at = os.getenv("WNDR_DIGEST_AT", "09:00")
    period = os.getenv("WNDR_DIGEST_PERIOD", "1d")
    topics = [t.strip() for t in
              os.getenv("WNDR_DIGEST_TOPICS", "questions_to_women,questions_to_men").split(",")
              if t.strip()]

    if args.now:
        logger.info("run-once: period=%s topics=%s", period, topics)
        run_once(topics, period)
        return

    logger.info("scheduler up: tz=%s at=%s period=%s topics=%s", tz.key, at, period, topics)
    while True:
        sleep_s = _seconds_until_next(at, tz)
        logger.info("next digest in %.0f min (%s %s)", sleep_s / 60, at, tz.key)
        time.sleep(sleep_s)
        run_once(topics, period)
        time.sleep(60)  # step past the target minute so we don't fire twice


if __name__ == "__main__":
    main()
