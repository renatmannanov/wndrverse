"""Unit tests for the digest date-range boundaries (digest-on-demand step 1).

Two layers, both DB-free:
  - parse_date_range: YYYY-MM-DD strings -> (since, until). This is where the
    INCLUSIVE from..till semantics live (until = till + 1 day, exclusive upper).
  - get_fragments_for_digest: that the `until` arg adds a `created_at < until`
    filter (via a fake SQLAlchemy session — no real DB, no pgvector).
"""

from datetime import datetime

import pytest

from delivery.cli import parse_date_range


# --- parse_date_range: the boundary math -----------------------------------

def test_range_inclusive_both_ends():
    since, until = parse_date_range("2026-05-01", "2026-05-31")
    assert since == datetime(2026, 5, 1, 0, 0, 0)
    # till + 1 day -> a 23:59 fragment on 2026-05-31 is < until, so included
    assert until == datetime(2026, 6, 1, 0, 0, 0)


def test_single_day_range():
    since, until = parse_date_range("2026-05-15", "2026-05-15")
    assert since == datetime(2026, 5, 15)
    assert until == datetime(2026, 5, 16)  # whole of the 15th is covered


def test_fragment_at_date_from_start_is_included():
    """A fragment exactly at date_from 00:00 satisfies created_at >= since."""
    since, until = parse_date_range("2026-05-01", "2026-05-31")
    frag_at_from = datetime(2026, 5, 1, 0, 0, 0)
    assert since <= frag_at_from < until


def test_fragment_at_2359_on_date_till_is_included():
    since, until = parse_date_range("2026-05-01", "2026-05-31")
    frag_late = datetime(2026, 5, 31, 23, 59, 59)
    assert since <= frag_late < until


def test_fragment_at_midnight_after_date_till_is_excluded():
    since, until = parse_date_range("2026-05-01", "2026-05-31")
    frag_next = datetime(2026, 6, 1, 0, 0, 0)
    assert not (frag_next < until)  # excluded — it's the next period


def test_bad_date_raises():
    with pytest.raises(ValueError):
        parse_date_range("2026-13-99", "2026-05-31")
    with pytest.raises(ValueError):
        parse_date_range("not-a-date", "2026-05-31")


def test_from_after_till_raises():
    with pytest.raises(ValueError):
        parse_date_range("2026-05-31", "2026-05-01")


# --- get_fragments_for_digest: the `until` filter is applied ----------------

class _FakeQuery:
    """Records each .filter() call without a DB. Always returns itself, then [].

    We don't assert on SQLAlchemy expression internals (brittle); we assert the
    number of filters grows when `until`/`since` are passed — i.e. the bounds are
    wired into the query.
    """
    def __init__(self, recorder):
        self.recorder = recorder

    def filter(self, *args):
        self.recorder.append(args)
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return []


class _FakeSession:
    def __init__(self, recorder):
        self.recorder = recorder

    def query(self, *args):
        return _FakeQuery(self.recorder)

    def close(self):
        pass


def _patched_count(monkeypatch, **call_kwargs):
    from core.store import fragments_db
    recorder = []
    monkeypatch.setattr(fragments_db, "SessionLocal",
                        lambda: _FakeSession(recorder))
    fragments_db.get_fragments_for_digest(**call_kwargs)
    return len(recorder)


def test_until_adds_a_filter(monkeypatch):
    base = _patched_count(monkeypatch, topic="t", since=None, until=None)
    with_until = _patched_count(
        monkeypatch, topic="t", since=None, until=datetime(2026, 6, 1))
    assert with_until == base + 1  # one extra filter: created_at < until


def test_since_and_until_both_add_filters(monkeypatch):
    base = _patched_count(monkeypatch, topic="t", since=None, until=None)
    both = _patched_count(
        monkeypatch, topic="t",
        since=datetime(2026, 5, 1), until=datetime(2026, 6, 1))
    assert both == base + 2  # since filter + until filter


def test_no_bounds_behaves_as_before(monkeypatch):
    """since=None, until=None -> no date filters added (whole corpus by topic)."""
    n = _patched_count(monkeypatch, topic="t", since=None, until=None)
    # base filters: is_duplicate, topic, min_chars = 3 (no date bounds)
    assert n == 3
