"""Map a Telegram source (chat_id, thread_id) -> topic name.

Two layouts, same key shape `(channel_id, message_thread_id)`:
  - now:   4 separate groups  -> (chat_id, None)
  - later: 1 supergroup w/ forum topics -> (chat_id, thread_id)
Switching layouts = new rows in the JSON, not new code.

Config path: env WNDR_TOPIC_MAP (default core/ingest/topic_map.json).
Loaded once and cached — not re-read per message.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "topic_map.json")

# Cache: { (channel_id, thread_id|None): topic }. None = not loaded yet.
_cache: dict | None = None


def _config_path() -> str:
    return os.getenv("WNDR_TOPIC_MAP") or _DEFAULT_PATH


def _load() -> dict:
    """Read the JSON config into a {(channel_id, thread_id): topic} dict.

    Missing/broken file -> empty map + warning (the bot must not die on start).
    """
    path = _config_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.warning("topic_map config not found at %s — empty map (all sources skipped)", path)
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("topic_map config at %s is broken (%s) — empty map", path, exc)
        return {}

    mapping: dict = {}
    for row in data.get("mappings", []):
        key = (row["channel_id"], row.get("thread_id"))
        mapping[key] = row["topic"]
    return mapping


def _get_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def reload() -> None:
    """Drop the cache so the next resolve_topic re-reads the file (tests / config edits)."""
    global _cache
    _cache = None


def resolve_topic(channel_id: int, thread_id: int | None) -> str | None:
    """Return the topic for a source, or None if unknown (caller skips + logs).

    Lookup order: exact (channel_id, thread_id) -> per-channel default (thread_id None) -> None.
    """
    cache = _get_cache()
    if (channel_id, thread_id) in cache:
        return cache[(channel_id, thread_id)]
    if (channel_id, None) in cache:           # per-channel default
        return cache[(channel_id, None)]
    return None
