"""
Ingest: load telegram-gather JSON exports into the fragments table.

This is the only data entry point in the MVP. The interface is shaped so a future
realtime source plugs in without changes — everything funnels into ingest().
"""

import os
import sys
import json
import glob
import logging

from core.ingest.normalize import message_to_fragment
from core.store.fragments_db import insert_fragments_batch

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


def ingest(messages: list[dict]) -> dict:
    """Insert already-normalized Fragment dicts in batches.

    Single funnel for any source (file now, bot/telethon later).
    Returns {'indexed': N, 'duplicates_skipped': N}.
    """
    indexed = 0
    skipped = 0
    for i in range(0, len(messages), _BATCH_SIZE):
        chunk = messages[i:i + _BATCH_SIZE]
        res = insert_fragments_batch(chunk)
        indexed += res['indexed']
        skipped += res['duplicates_skipped']
    return {'indexed': indexed, 'duplicates_skipped': skipped}


def _iter_thread_messages(thread: dict):
    """Yield (msg, thread_root_id) for a thread, handling null-root threads.

    Every export file has exactly one thread with root=None whose replies are
    still valid — they must be ingested with thread_root_id=None.
    """
    root = thread.get('root')
    if root is not None:
        thread_root_id = root.get('id')
        yield root, thread_root_id
    else:
        thread_root_id = None  # null-root: replies kept, root skipped

    for reply in (thread.get('replies') or []):
        yield reply, thread_root_id


def load_export_file(path: str) -> int:
    """Read one JSON export, flatten threads → messages, normalize, insert.

    Returns number of fragments inserted.
    """
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)

    topic = data.get('topic_name') or 'unknown'
    chat_name = data.get('chat_name') or 'wndr'
    chat_id = data.get('chat_id')   # None for OLD exports (no field) — legacy key

    fragments = []
    skipped_no_text = 0
    no_user_id = 0

    for thread in data.get('threads', []):
        for msg, thread_root_id in _iter_thread_messages(thread):
            frag = message_to_fragment(
                msg, topic=topic, chat_name=chat_name, chat_id=chat_id,
                thread_root_id=thread_root_id,
            )
            if frag is None:
                skipped_no_text += 1
                continue
            if frag['sender_id'] is None:
                no_user_id += 1
            fragments.append(frag)

    res = ingest(fragments)
    logger.info(
        "%s: %d inserted, %d dup-skipped, %d no-text-skipped, %d without user_id (of %d)",
        topic, res['indexed'], res['duplicates_skipped'], skipped_no_text,
        no_user_id, len(fragments),
    )
    return res['indexed']


def load_export_dir(dir_path: str, topics: list[str] | None = None) -> int:
    """Walk wndr_topic_*.json in dir_path (or only the given topics). Returns total inserted."""
    total = 0
    pattern = os.path.join(dir_path, "wndr_topic_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        logger.warning("No wndr_topic_*.json found in %s", dir_path)
    for path in files:
        # topic from filename: wndr_topic_<name>.json
        name = os.path.basename(path)[len("wndr_topic_"):-len(".json")]
        if topics and name not in topics:
            continue
        total += load_export_file(path)
    logger.info("Done: %d fragments inserted from %s", total, dir_path)
    return total


def _main(argv: list[str]) -> int:
    import argparse

    try:
        from dotenv import load_dotenv
        load_dotenv()  # so WNDR_EXPORTS_DIR from .env is available
    except ImportError:
        pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingest telegram-gather exports into fragments")
    parser.add_argument("--dir", default=os.getenv("WNDR_EXPORTS_DIR"),
                        help="Directory with wndr_topic_*.json (or env WNDR_EXPORTS_DIR)")
    parser.add_argument("--topic", action="append", default=None,
                        help="Limit to topic name(s); repeatable. Default: all topics.")
    args = parser.parse_args(argv)

    if not args.dir:
        parser.error("--dir or env WNDR_EXPORTS_DIR is required")

    load_export_dir(args.dir, topics=args.topic)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
