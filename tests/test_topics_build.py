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
    # Hour gaps everywhere: same-author messages closer than SERIES_GAP_S would
    # series-merge into one document and shrink the doc count below what
    # UMAP+HDBSCAN needs on synthetic data.
    # cloud A: 6 msgs, 3 authors, many likes → hotter
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) + 1.0).tolist()
        frags.append(_frag(i, v, sender=100 + (i % 3), text=txt + f" A{i}",
                            reactions=[{'count': 5, 'emoji': 'x'}],
                            ts=f"2026-05-01T0{i}:00:00"))
    # cloud B: 5 msgs, 3 authors, no likes → cooler
    for i in range(5):
        v = (rng.normal(0, 0.01, 1536) - 1.0).tolist()
        frags.append(_frag(20 + i, v, sender=200 + (i % 3), text=txt + f" B{i}",
                            ts=f"2026-05-02T0{i}:00:00"))

    out = build_topics(frags, min_authors=2)
    assert len(out) == 2
    # hotter cloud (more msgs + likes) ranked first
    assert out[0]['msgs'] >= out[1]['msgs']
    for t in out:
        assert set(t.keys()) == {'name', 'msgs', 'anchor_channel_id', 'anchor_external_id'}
        assert t['name'] == "стаб-тема"


def test_anchor_skips_loose_early_member(monkeypatch):
    """The anchor is the earliest TIGHT member; a loose early stray must not win.

    Doesn't run real clustering — drives build_topics' grouping via a stubbed
    cluster_embeddings so probabilities are exact and deterministic.
    """
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "x")
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата")
    # 4 fragments, one cluster: the EARLIEST one is loosely attached (p=0.5),
    # the next-earliest tight one (p=0.95) must become the anchor.
    frags = [
        _frag(0, [0.0] * 4, sender=1, text=txt + " stray",
              ts="2026-05-01T00:00:00"),
        _frag(1, [0.0] * 4, sender=2, text=txt + " core1",
              ts="2026-05-02T00:00:00"),
        _frag(2, [0.0] * 4, sender=1, text=txt + " core2",
              ts="2026-05-03T00:00:00"),
        _frag(3, [0.0] * 4, sender=2, text=txt + " core3",
              ts="2026-05-04T00:00:00"),
    ]
    monkeypatch.setattr(
        topics_mod, "cluster_embeddings",
        lambda vectors, **k: ([0, 0, 0, 0], [0.5, 0.95, 1.0, 1.0]))
    out = build_topics(frags, min_authors=2)
    assert len(out) == 1
    # tg_..._1001 = fragment id 1 (earliest with prob >= 0.9), NOT the stray 1000
    assert out[0]['anchor_external_id'] == 'tg_-1002924475859_1001'
    # the stray still counts as a member (only the anchor changed)
    assert out[0]['msgs'] == 4


def test_anchor_falls_back_when_no_tight_members(monkeypatch):
    """All members loose (< 0.9) -> plain earliest wins (no crash, no empty)."""
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "x")
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата")
    frags = [
        _frag(i, [0.0] * 4, sender=1 + (i % 2), text=txt + f" m{i}",
              ts=f"2026-05-0{i + 1}T00:00:00")
        for i in range(3)
    ]
    monkeypatch.setattr(
        topics_mod, "cluster_embeddings",
        lambda vectors, **k: ([0, 0, 0], [0.5, 0.6, 0.7]))
    out = build_topics(frags, min_authors=2)
    assert len(out) == 1
    assert out[0]['anchor_external_id'] == 'tg_-1002924475859_1000'  # earliest


def test_chain_msgs_exclude_reactions_likes_include(monkeypatch):
    """A series (long + 2 short reply-reactions with likes) + a second separate
    cluster: msgs of the thread topic does NOT count reactions, likes DO include
    the reactions' likes, anchor = the series root."""
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "x")
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата")

    def _chain_frag(i, vec, sender, text, reply_to=None, reactions=None, ts=None):
        f = _frag(i, vec, sender, text, reactions=reactions, ts=ts)
        f['msg_id'] = str(1000 + i)
        if reply_to is not None:
            f['reply_to_msg_id'] = str(reply_to)
        return f

    frags = [
        # thread: 1 long root + a long reply + 2 short reactions with likes
        _chain_frag(0, [1.0, 0.0], sender=1, text=txt + " root",
                    ts="2026-05-01T00:00:00"),
        _chain_frag(1, [1.0, 0.05], sender=2, text=txt + " ответ по сути",
                    reply_to=1000, ts="2026-05-01T01:00:00"),
        _chain_frag(2, [0.0, 9.0], sender=3, text="спасибо, супер",
                    reply_to=1000, reactions=[{'count': 4, 'emoji': 'a'}],
                    ts="2026-05-01T02:00:00"),
        _chain_frag(3, [0.0, 8.0], sender=4, text="класс, огонь",
                    reply_to=1001, reactions=[{'count': 6, 'emoji': 'b'}],
                    ts="2026-05-01T03:00:00"),
        # second, unrelated cluster (2 docs far away in vector space)
        _chain_frag(10, [-1.0, 0.0], sender=5, text=txt + " другая тема",
                    ts="2026-05-02T00:00:00"),
        _chain_frag(11, [-1.0, 0.05], sender=6, text=txt + " тоже другая",
                    ts="2026-05-02T05:00:00"),
    ]
    # 3 docs: [thread of 4 msgs], [10], [11] — stub clustering: thread+nothing
    # else in cluster 0, docs 10/11 in cluster 1
    monkeypatch.setattr(
        topics_mod, "cluster_embeddings",
        lambda vectors, **k: ([0, 1, 1], [1.0, 1.0, 1.0]))
    out = build_topics(frags, min_authors=1, min_cluster_size=1)
    thread = next(t for t in out if t['anchor_external_id'] == 'tg_-1002924475859_1000')
    assert thread['msgs'] == 2                      # root + substantive reply only
    assert thread['anchor_external_id'] == 'tg_-1002924475859_1000'  # series root


def test_reaction_texts_dont_glue_two_conversations(monkeypatch):
    """Two conversations whose reaction texts share the same lexicon (vectors
    mid-way between the clouds): before chains those reactions were standalone
    points bridging the clouds; now each one rides its thread's document, whose
    length-weighted embedding stays near the substantive root — 2 topics, not 1."""
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "x")
    rng = np.random.default_rng(3)
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата ") * 3
    # >= 80 chars and substantive: in the OLD pipeline this passed the flood-
    # filter as its own clustering point (the mega-glue defect's mechanics)
    react_txt = ("спасибо огромное за такой развёрнутый и полезный пост, "
                 "очень откликнулось и сильно помогло")

    def _chain_frag(i, vec, sender, text, reply_to=None, ts=None):
        f = _frag(i, vec, sender, text, ts=ts)
        f['msg_id'] = str(1000 + i)
        if reply_to is not None:
            f['reply_to_msg_id'] = str(reply_to)
        return f

    frags = []
    # conversation A: 6 roots near +1, each with a reply-reaction mid-way (0)
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) + 1.0).tolist()
        frags.append(_chain_frag(i, v, sender=100 + i, text=txt + f" A{i}",
                                 ts=f"2026-05-01T0{i}:00:00"))
        rv = rng.normal(0, 0.01, 1536).tolist()
        frags.append(_chain_frag(10 + i, rv, sender=150 + i, text=react_txt,
                                 reply_to=1000 + i,
                                 ts=f"2026-05-01T0{i}:30:00"))
    # conversation B: 6 roots near -1, same-lexicon reactions mid-way too
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) - 1.0).tolist()
        frags.append(_chain_frag(30 + i, v, sender=200 + i, text=txt + f" B{i}",
                                 ts=f"2026-05-03T0{i}:00:00"))
        rv = rng.normal(0, 0.01, 1536).tolist()
        frags.append(_chain_frag(40 + i, rv, sender=250 + i, text=react_txt,
                                 reply_to=1030 + i,
                                 ts=f"2026-05-03T0{i}:30:00"))

    out = build_topics(frags, min_authors=2)
    # 24 fragments → 12 documents; reactions ride their threads, the weighted
    # doc embeddings stay near ±1 → two separate topics survive
    assert len(out) == 2


def test_monologue_dropped(monkeypatch):
    monkeypatch.setattr(topics_mod, "complete", lambda *a, **k: "x")
    rng = np.random.default_rng(2)
    txt = ("осмысленный длинный текст про важную тему сообщества и подробное "
           "обсуждение деталей разных аспектов вопроса участниками чата")
    frags = []
    # cloud A: single author (a monologue) → must be dropped by min_authors=2.
    # Hour gaps (> SERIES_GAP_S) keep the 6 messages as 6 separate documents —
    # minute gaps would series-merge them into ONE doc and this test would stop
    # exercising min_authors (it'd drop as HDBSCAN noise instead).
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) + 1.0).tolist()
        frags.append(_frag(i, v, sender=999, text=txt + f" A{i}",
                            ts=f"2026-05-01T0{i}:00:00"))
    # cloud B: 3 authors → a real topic (also gives UMAP non-degenerate
    # structure); hour gaps so same-author messages don't series-merge
    for i in range(6):
        v = (rng.normal(0, 0.01, 1536) - 1.0).tolist()
        frags.append(_frag(20 + i, v, sender=200 + (i % 3), text=txt + f" B{i}",
                            ts=f"2026-05-02T0{i}:00:00"))
    out = build_topics(frags, min_authors=2)
    # only cloud B survives; cloud A's single-author cluster is filtered out
    assert len(out) == 1
