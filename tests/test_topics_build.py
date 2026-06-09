"""Unit tests for core.brain.topics.build_topics — no real DB, LLM stubbed.

Synthetic vectors + texts; the LLM name call is monkeypatched so no OpenAI spend.
"""

import numpy as np
import pytest

import core.brain.topics as topics_mod
from core.brain.topics import _is_substantive, build_topics


def test_is_substantive():
    assert _is_substantive("+") is False
    assert _is_substantive("ахаха") is False           # one repeated word
    assert _is_substantive("🔥🔥🔥🔥") is False          # emoji only
    assert _is_substantive(
        "сегодня обсуждали будущее SaaS и как меняется рынок продуктов"
    ) is True


def _frag(i, vec, sender, text, reactions=None, ts="2026-05-01T00:00:00"):
    return {
        'id': i, 'text': text, 'created_at': ts, 'sender_id': sender,
        'embedding': vec, 'channel_id': -1002924475859,
        'external_id': f'tg_-1002924475859_{1000 + i}',
        'reactions': reactions, 'tags': [],
    }


def test_build_topics_two_clusters_ranked(monkeypatch):
    # stub the LLM name so there's no spend; return a deterministic name
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "стаб-тема")

    rng = np.random.default_rng(1)
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата")

    frags = []
    # cloud A: 6 msgs, 3 authors, many likes → hotter
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) + 1.0).tolist()
        frags.append(_frag(i, v, sender=100 + (i % 3), text=txt + f" A{i}",
                            reactions=[{'count': 5, 'emoji': 'x'}],
                            ts=f"2026-05-01T00:0{i}:00"))
    # cloud B: 5 msgs, 3 authors, no likes → cooler
    for i in range(5):
        v = (rng.normal(0, 0.01, 1536) - 1.0).tolist()
        frags.append(_frag(20 + i, v, sender=200 + (i % 3), text=txt + f" B{i}",
                            ts=f"2026-05-02T00:0{i}:00"))

    out = build_topics(frags, min_authors=2)
    assert len(out) == 2
    # hotter cloud (more msgs + likes) ranked first
    assert out[0]['msgs'] >= out[1]['msgs']
    for t in out:
        assert set(t.keys()) == {'name', 'msgs', 'anchor_channel_id', 'anchor_external_id'}
        assert t['name'] == "стаб-тема"


def test_monologue_dropped(monkeypatch):
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "x")
    rng = np.random.default_rng(2)
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата")
    frags = []
    # cloud A: single author (a monologue) → must be dropped by min_authors=2
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) + 1.0).tolist()
        frags.append(_frag(i, v, sender=999, text=txt + f" A{i}",
                            ts=f"2026-05-01T00:0{i}:00"))
    # cloud B: 3 authors → a real topic (also gives UMAP non-degenerate structure)
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) - 1.0).tolist()
        frags.append(_frag(20 + i, v, sender=200 + (i % 3), text=txt + f" B{i}",
                            ts=f"2026-05-02T00:0{i}:00"))
    out = build_topics(frags, min_authors=2)
    # only cloud B survives; cloud A's single-author cluster is filtered out
    assert len(out) == 1
