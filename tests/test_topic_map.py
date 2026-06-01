"""Unit tests for core.ingest.topic_map.resolve_topic (source -> topic lookup).

Path comes from conftest.py at repo root — no sys.path hacks here.
"""

import json
import os

import pytest

from core.ingest import topic_map


@pytest.fixture
def mapped(tmp_path, monkeypatch):
    """Write a config to a temp path, point WNDR_TOPIC_MAP at it, reset cache."""
    def _write(mappings):
        cfg = tmp_path / "topic_map.json"
        cfg.write_text(json.dumps({"mappings": mappings}), encoding="utf-8")
        monkeypatch.setenv("WNDR_TOPIC_MAP", str(cfg))
        topic_map.reload()
        return cfg
    yield _write
    topic_map.reload()  # don't leak cache into other tests


def test_exact_pair(mapped):
    mapped([{"channel_id": -100, "thread_id": 7, "topic": "deep"}])
    assert topic_map.resolve_topic(-100, 7) == "deep"


def test_channel_default_thread_none(mapped):
    mapped([{"channel_id": -100, "thread_id": None, "topic": "men"}])
    assert topic_map.resolve_topic(-100, None) == "men"


def test_falls_back_to_channel_default(mapped):
    # only a (chat, None) default exists; an unknown thread on that chat -> default
    mapped([{"channel_id": -100, "thread_id": None, "topic": "men"}])
    assert topic_map.resolve_topic(-100, 999) == "men"


def test_exact_pair_wins_over_default(mapped):
    mapped([
        {"channel_id": -100, "thread_id": None, "topic": "men"},
        {"channel_id": -100, "thread_id": 7, "topic": "deep"},
    ])
    assert topic_map.resolve_topic(-100, 7) == "deep"
    assert topic_map.resolve_topic(-100, 3) == "men"


def test_unknown_channel_returns_none(mapped):
    mapped([{"channel_id": -100, "thread_id": None, "topic": "men"}])
    assert topic_map.resolve_topic(-999, None) is None


def test_wndr_forum_topics(mapped):
    # WNDR supergroup: forum topics, no (chat, None) default -> unknown thread is None.
    mapped([
        {"channel_id": -1002924475859, "thread_id": 16139, "topic": "questions_to_women"},
        {"channel_id": -1002924475859, "thread_id": 16138, "topic": "questions_to_men"},
    ])
    assert topic_map.resolve_topic(-1002924475859, 16139) == "questions_to_women"
    assert topic_map.resolve_topic(-1002924475859, 16138) == "questions_to_men"
    # no per-channel default for this chat -> unknown thread falls through to None
    assert topic_map.resolve_topic(-1002924475859, 99999) is None


def test_missing_file_is_empty_not_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("WNDR_TOPIC_MAP", str(tmp_path / "does_not_exist.json"))
    topic_map.reload()
    assert topic_map.resolve_topic(-100, None) is None
    topic_map.reload()


def test_broken_json_is_empty_not_crash(tmp_path, monkeypatch):
    bad = tmp_path / "topic_map.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setenv("WNDR_TOPIC_MAP", str(bad))
    topic_map.reload()
    assert topic_map.resolve_topic(-100, None) is None
    topic_map.reload()
