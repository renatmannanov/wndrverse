"""Unit tests for author grouping + [@N] -> [name] substitution.

DB-free, OpenAI-free. Covers the digest-group-by-author feature:
  - _group_by_author: one [@N] block per author, all texts joined, names absent
    from the LLM input (PII), N numbered by first-message date.
  - humanize_author_refs: [@N] -> [name] locally, no date, unknown N untouched.
  - build_digest: wires synthesize_and_save's author_refs through the new path
    ([@N] -> [name]) and never falls back to the legacy humanize_refs.
  - synthesize_and_save passes author_refs through untouched.
  - _insufficient_data_message (<3): self-contained, no [#id]/[@N] refs.
"""

import re
from datetime import datetime

import pytest

from core.brain import synthesis
from delivery import cli


# --- _group_by_author -------------------------------------------------------

def _frag(id, text, created_at, sender_id=None, author_name=None, username=None):
    return {"id": id, "text": text, "created_at": created_at,
            "sender_id": sender_id, "author_name": author_name, "username": username}


def test_one_author_three_messages_one_block():
    frags = [
        _frag(1, "первая мысль", "2026-05-16T10:00", sender_id=42, author_name="Катя"),
        _frag(2, "вторая мысль", "2026-05-17T10:00", sender_id=42, author_name="Катя"),
        _frag(3, "третья мысль", "2026-05-18T10:00", sender_id=42, author_name="Катя"),
    ]
    text, refs = synthesis._group_by_author(frags)
    # one [@1] block, three texts joined by ---
    assert text.count("[@1]") == 1
    assert "[@2]" not in text
    assert text.count("---") == 2
    assert "первая мысль" in text and "вторая мысль" in text and "третья мысль" in text
    assert "3 сообщ." in text
    assert refs == {1: "Катя"}


def test_two_authors_numbered_by_first_message_date():
    frags = [
        _frag(10, "B первый", "2026-05-18T10:00", sender_id=2, author_name="Боря"),
        _frag(11, "A первый", "2026-05-16T10:00", sender_id=1, author_name="Аня"),
        _frag(12, "A второй", "2026-05-20T10:00", sender_id=1, author_name="Аня"),
    ]
    text, refs = synthesis._group_by_author(frags)
    # Аня's first message (05-16) predates Бори's (05-18) -> Аня is @1
    assert refs == {1: "Аня", 2: "Боря"}
    # @1 block appears before @2 block in the text
    assert text.index("[@1]") < text.index("[@2]")


def test_names_never_in_grouped_text_pii():
    frags = [
        _frag(1, "текст один", "2026-05-16T10:00", sender_id=42, author_name="Катя Базылева"),
        _frag(2, "текст два", "2026-05-17T10:00", sender_id=7, author_name="Иван Петров"),
    ]
    text, refs = synthesis._group_by_author(frags)
    # the LLM input must carry NO author names — PII never leaves the process
    assert "Катя" not in text
    assert "Базылева" not in text
    assert "Иван" not in text
    # names live only in author_refs (local)
    assert set(refs.values()) == {"Катя Базылева", "Иван Петров"}


def test_anonymous_each_its_own_author():
    frags = [
        _frag(1, "аноним раз", "2026-05-16T10:00", sender_id=None, author_name=None),
        _frag(2, "аноним два", "2026-05-17T10:00", sender_id=None, author_name=None),
    ]
    text, refs = synthesis._group_by_author(frags)
    # can't tell anonymous messages apart -> each is its own [@N]
    assert refs == {1: "аноним", 2: "аноним"}
    assert "[@1]" in text and "[@2]" in text


def test_single_message_head_has_no_count():
    frags = [_frag(1, "одна", "2026-05-16T10:00", sender_id=1, author_name="Аня")]
    text, refs = synthesis._group_by_author(frags)
    assert "сообщ." not in text          # no "(k сообщ.)" for a single message
    assert text.startswith("[@1]:")


# --- _display_name (Name @handle) -------------------------------------------

def test_display_name_with_handle():
    f = _frag(1, "t", "2026-05-16T10:00", sender_id=1, author_name="Нелли", username="Nelli_Logar")
    assert synthesis._display_name(f) == "Нелли @Nelli_Logar"


def test_display_name_no_handle_falls_back_to_name():
    f = _frag(1, "t", "2026-05-16T10:00", sender_id=1, author_name="Аня", username=None)
    assert synthesis._display_name(f) == "Аня"


def test_display_name_anonymous():
    f = _frag(1, "t", "2026-05-16T10:00", sender_id=None, author_name=None, username=None)
    assert synthesis._display_name(f) == "аноним"


def test_group_by_author_handle_in_refs():
    frags = [
        _frag(1, "a", "2026-05-16T10:00", sender_id=1, author_name="Нелли", username="Nelli_Logar"),
        _frag(2, "b", "2026-05-17T10:00", sender_id=2, author_name="Аня", username=None),
    ]
    text, refs = synthesis._group_by_author(frags)
    assert refs == {1: "Нелли @Nelli_Logar", 2: "Аня"}
    # PII: neither name nor handle reaches the LLM input
    assert "Нелли" not in text and "Nelli_Logar" not in text and "Аня" not in text


# --- humanize_author_refs ---------------------------------------------------

def test_humanize_basic_substitution_no_brackets():
    # display string is substituted WITHOUT brackets, so a trailing @handle auto-links
    out = cli.humanize_author_refs(
        "[@1] — предлагает; [@2] — просит",
        {1: "Нелли @Nelli_Logar", 2: "Аня"})
    assert out == "Нелли @Nelli_Logar — предлагает; Аня — просит"
    assert "[@1]" not in out and "[@2]" not in out


def test_humanize_handle_is_bare_for_autolink():
    out = cli.humanize_author_refs("[@1] про баланс", {1: "Катя @katya_k"})
    assert "@katya_k" in out
    assert "[@katya_k]" not in out       # no brackets around the mention


def test_humanize_unknown_ref_left_as_is():
    out = cli.humanize_author_refs("[@1] и [@9]", {1: "Аня"})
    assert "Аня" in out
    assert "[@9]" in out                 # unknown N untouched, doesn't crash


def test_humanize_string_keys_tolerated():
    # JSON round-trip could turn int keys into strings
    out = cli.humanize_author_refs("[@1]", {"1": "Аня"})
    assert out == "Аня"


# --- build_digest wiring (the obligatory regression test) -------------------

def test_build_digest_substitutes_author_refs_not_ids(monkeypatch):
    monkeypatch.setattr(cli, "get_fragments_for_digest",
                        lambda **k: [_frag(1, "x", "2026-05-16T10:00")])

    def fake_synth(topic_arg, fragments, topic_type=None):
        return {
            "content": "📌 [@1] — мысль; [@2] — другая",
            "fragment_ids": [1, 2],
            "author_refs": {1: "Аня", 2: "Боря"},
            "found": 2, "used": 2, "model": "x",
        }
    monkeypatch.setattr(cli, "synthesize_and_save", fake_synth)
    # legacy path must NOT run — blow up if it does
    monkeypatch.setattr(cli, "humanize_refs",
                        lambda *a, **k: pytest.fail("humanize_refs must not be called"))

    since = datetime(2026, 5, 16)
    until = datetime(2026, 6, 1)  # exclusive -> last day 05-31
    result = cli.build_digest("commits", since, until)
    assert result is not None
    # display strings substituted WITHOUT brackets (so @handles auto-link)
    assert "Аня" in result["text"] and "Боря" in result["text"]
    assert "[@1]" not in result["text"] and "[@2]" not in result["text"]
    # deterministic header: topic + exact dates (from the request, not the LLM)
    assert "commits" in result["text"]
    assert "2026-05-16" in result["text"] and "2026-05-31" in result["text"]
    assert result["text"].index("commits") < result["text"].index("Аня")  # header first


# --- _digest_header ---------------------------------------------------------

def test_header_exact_range():
    # until is EXCLUSIVE -> last shown day is until - 1
    h = cli._digest_header("commits", datetime(2026, 5, 16), datetime(2026, 6, 1))
    assert h == "📅 commits · 2026-05-16 — 2026-05-31"


def test_header_open_upper_bound():
    h = cli._digest_header("offerings", datetime(2026, 5, 1), None)
    assert "2026-05-01" in h and "сейчас" in h


def test_header_open_lower_bound():
    h = cli._digest_header("all", None, datetime(2026, 6, 1))
    assert "…" in h and "2026-05-31" in h


# --- synthesize_and_save passes author_refs through -------------------------

def test_synthesize_and_save_keeps_author_refs(monkeypatch):
    monkeypatch.setattr(synthesis, "synthesize",
                        lambda *a, **k: {"content": "c", "fragment_ids": [1],
                                         "author_refs": {1: "Аня"}, "found": 1,
                                         "model": "x"})
    monkeypatch.setattr(synthesis, "save_artifact", lambda **k: 99)
    out = synthesis.synthesize_and_save("commits", [_frag(1, "x", "2026-05-16T10:00")])
    assert out["author_refs"] == {1: "Аня"}     # not dropped
    assert out["artifact_id"] == 99


# --- _insufficient_data_message (<3) ----------------------------------------

def test_insufficient_message_self_contained():
    frags = [
        _frag(1, "короткое сообщение", "2026-05-16T10:00", sender_id=5,
              author_name="Аня", username="anya_k"),
        _frag(2, "ещё одно", "2026-05-17T10:00", sender_id=None, author_name=None),
    ]
    msg = synthesis._insufficient_data_message("commits", frags)
    # no leftover ref syntax — this branch never goes through substitution
    assert "[#" not in msg
    assert "[@" not in msg
    # display name (Name @handle) shown directly, plus 'аноним' fallback
    assert "Аня @anya_k" in msg
    assert "аноним" in msg
