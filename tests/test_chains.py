"""Unit tests for core.brain.chains.build_chains — pure synthetic dicts, no DB."""

import numpy as np

from core.brain.chains import build_chains

LONG = ("осмысленный длинный текст про важную тему сообщества и подробное "
        "обсуждение деталей разных аспектов вопроса участниками чата")


def _frag(i, sender=1, text=LONG, ts="2026-05-01T00:00:00", msg_id=None,
          reply_to=None, vec=None, reactions=None):
    f = {
        'id': i, 'text': text, 'created_at': ts, 'sender_id': sender,
        'embedding': vec if vec is not None else [1.0, 0.0],
        'channel_id': -100500, 'external_id': f'tg_-100500_{1000 + i}',
        'reactions': reactions, 'tags': [],
    }
    # msg_id/reply_to_msg_id deliberately OPTIONAL — old tests' dicts lack them
    if msg_id is not None:
        f['msg_id'] = msg_id
    if reply_to is not None:
        f['reply_to_msg_id'] = reply_to
    return f


def test_reply_pair_merges():
    frags = [
        _frag(0, sender=1, msg_id="10", ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="10", ts="2026-05-01T05:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 1
    assert len(docs[0]['messages']) == 2


def test_reply_to_missing_parent_ignored():
    frags = [
        _frag(0, sender=1, msg_id="10", ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="999", ts="2026-05-01T05:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 2


def test_reply_chain_depth_3():
    frags = [
        _frag(0, sender=1, msg_id="10", ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="10", ts="2026-05-01T05:00:00"),
        _frag(2, sender=3, msg_id="12", reply_to="11", ts="2026-05-01T10:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 1
    assert [m['id'] for m in docs[0]['messages']] == [0, 1, 2]


def test_series_same_author_small_gap_merges():
    frags = [
        _frag(i, sender=7, ts=f"2026-05-01T00:0{i}:00") for i in range(3)  # 60s gaps
    ]
    docs = build_chains(frags)
    assert len(docs) == 1


def test_series_large_gap_does_not_merge():
    frags = [
        _frag(0, sender=7, ts="2026-05-01T00:00:00"),
        _frag(1, sender=7, ts="2026-05-01T00:06:40"),   # 400s
        _frag(2, sender=7, ts="2026-05-01T00:13:20"),   # 400s
    ]
    docs = build_chains(frags)
    assert len(docs) == 3


def test_series_survives_interleaved_other_author():
    """Another author's message between two series parts (real case: 14068
    landed between longread parts 14067/14069 in the same second) must NOT
    break the series — adjacency is per-sender, not global-timeline."""
    frags = [
        _frag(0, sender=7, msg_id="14067", ts="2026-05-01T00:00:00"),
        _frag(1, sender=9, msg_id="14068", ts="2026-05-01T00:00:00"),  # interleaved
        _frag(2, sender=7, msg_id="14069", ts="2026-05-01T00:00:16"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 2
    series = next(d for d in docs if len(d['messages']) == 2)
    assert {m['msg_id'] for m in series['messages']} == {"14067", "14069"}


def test_series_different_authors_not_merged():
    frags = [
        _frag(0, sender=1, ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, ts="2026-05-01T00:01:00"),
        _frag(2, sender=3, ts="2026-05-01T00:02:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 3


def test_longread_case_series_plus_replies():
    """3 long parts in a row (no reply between them) + reply-replies to each
    part → ONE document, root = first part."""
    frags = [
        _frag(0, sender=1, msg_id="14067", ts="2026-05-01T00:00:00"),
        _frag(1, sender=1, msg_id="14069", ts="2026-05-01T00:02:00"),
        _frag(2, sender=1, msg_id="14070", ts="2026-05-01T00:04:00"),
        _frag(3, sender=2, msg_id="14082", reply_to="14067",
              text="спасибо за лонгрид!", ts="2026-05-01T01:00:00"),
        _frag(4, sender=3, msg_id="14095", reply_to="14069",
              text="супер пост", ts="2026-05-01T02:00:00"),
        _frag(5, sender=4, msg_id="14101", reply_to="14070",
              text="огонь, спасибо", ts="2026-05-01T03:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 1
    assert docs[0]['root']['msg_id'] == "14067"
    assert len(docs[0]['messages']) == 6


def test_substantive_subset_and_embedding_of_long_only():
    """Short reactions (<80) around one long message: substantive == [long],
    embedding == the long message's embedding."""
    frags = [
        _frag(0, sender=1, msg_id="10", vec=[0.5, 0.5], ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="10", text="класс, спасибо тебе",
              vec=[9.0, 9.0], ts="2026-05-01T01:00:00"),
        _frag(2, sender=3, msg_id="12", reply_to="10", text="вот это да, мощно",
              vec=[8.0, 8.0], ts="2026-05-01T02:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 1
    assert [m['id'] for m in docs[0]['substantive']] == [0]
    assert docs[0]['embedding'] == [0.5, 0.5]
    assert len(docs[0]['messages']) == 3


def test_all_short_document_dropped():
    frags = [
        _frag(0, sender=1, msg_id="10", text="спасибо большое вам",
              ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="10", text="и тебе спасибо да",
              ts="2026-05-01T01:00:00"),
    ]
    assert build_chains(frags) == []


def test_embedding_weighted_by_length():
    """Two substantive texts of different lengths → mean shifted to the longer."""
    short_sub = LONG[:90]            # 90 chars, substantive
    long_sub = LONG + " " + LONG     # ~2x longer
    frags = [
        _frag(0, sender=1, msg_id="10", text=short_sub, vec=[0.0, 0.0],
              ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="10", text=long_sub,
              vec=[1.0, 1.0], ts="2026-05-01T01:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 1
    expected = len(long_sub) / (len(short_sub) + len(long_sub))
    assert np.allclose(docs[0]['embedding'], [expected, expected])
    assert expected > 0.5  # shifted toward the longer text


def test_root_is_earliest_even_if_short():
    frags = [
        _frag(0, sender=1, msg_id="10", text="привет всем тут", vec=[2.0, 2.0],
              ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, msg_id="11", reply_to="10", vec=[0.5, 0.5],
              ts="2026-05-01T01:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 1
    assert docs[0]['root']['id'] == 0          # earliest, even though short
    assert [m['id'] for m in docs[0]['substantive']] == [1]


def test_dicts_without_msg_id_keys_survive():
    """Synthetic dicts of older tests have no msg_id/reply_to_msg_id — that
    means 'no reply links', not a crash."""
    frags = [
        _frag(0, sender=1, ts="2026-05-01T00:00:00"),
        _frag(1, sender=2, ts="2026-05-02T00:00:00"),
    ]
    docs = build_chains(frags)
    assert len(docs) == 2
