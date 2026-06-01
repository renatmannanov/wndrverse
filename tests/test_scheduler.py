"""Unit tests for digest.scheduler — timing math + run_once orchestration.

run_once's collaborators (get_fragments_for_digest, _run_digest, parse_period)
are module-level in scheduler.py, so we monkeypatch scheduler.<name>. No DB, no
OpenAI, no Telegram.
"""

from zoneinfo import ZoneInfo

import pytest

from digest import scheduler


def test_seconds_until_next_in_range():
    s = scheduler._seconds_until_next("09:00", ZoneInfo("Asia/Almaty"))
    assert isinstance(s, float)
    assert 0 < s <= 86400


def test_run_once_calls_digest_per_topic(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "parse_period", lambda p: None)
    monkeypatch.setattr(scheduler, "get_fragments_for_digest",
                        lambda topic, since: [{"id": 1}])  # non-empty
    monkeypatch.setattr(scheduler, "_run_digest",
                        lambda topic, period, channel: calls.append((topic, period, channel)))

    scheduler.run_once(["t1", "t2"], "1d")

    assert calls == [("t1", "1d", "telegram_dm"), ("t2", "1d", "telegram_dm")]


def test_run_once_skips_empty_topic(monkeypatch):
    """guard (V1): topic with 0 fragments -> _run_digest NOT called for it."""
    calls = []
    frags = {"t1": [], "t2": [{"id": 9}]}
    monkeypatch.setattr(scheduler, "parse_period", lambda p: None)
    monkeypatch.setattr(scheduler, "get_fragments_for_digest",
                        lambda topic, since: frags[topic])
    monkeypatch.setattr(scheduler, "_run_digest",
                        lambda topic, period, channel: calls.append(topic))

    scheduler.run_once(["t1", "t2"], "1d")

    assert calls == ["t2"]  # t1 skipped (empty), t2 synthesized


def test_run_once_one_failure_does_not_stop_others(monkeypatch):
    """A topic that raises is logged and skipped; the next topic still runs."""
    calls = []
    monkeypatch.setattr(scheduler, "parse_period", lambda p: None)
    monkeypatch.setattr(scheduler, "get_fragments_for_digest",
                        lambda topic, since: [{"id": 1}])

    def _run(topic, period, channel):
        if topic == "boom":
            raise RuntimeError("synthesis exploded")
        calls.append(topic)

    monkeypatch.setattr(scheduler, "_run_digest", _run)

    scheduler.run_once(["boom", "ok"], "1d")

    assert calls == ["ok"]  # boom raised, ok still ran
