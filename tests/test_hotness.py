"""Unit tests for core.brain.hotness — pure reaction/score functions, no DB/LLM."""

from core.brain.hotness import likes_of, cluster_stats, chain_cluster_stats, score


def test_likes_of():
    assert likes_of(None) == 0
    assert likes_of([]) == 0
    assert likes_of([{'count': 4, 'emoji': '❤'}, {'count': 2, 'emoji': '\U0001f4af'}]) == 6
    assert likes_of([{'emoji': 'x'}]) == 0          # no count — doesn't crash
    assert likes_of([{'count': 'nan', 'emoji': 'x'}]) == 0  # bad count type — skipped
    assert likes_of(['garbage']) == 0               # non-dict item — skipped


def test_cluster_stats():
    members = [
        {'sender_id': 1, 'reactions': [{'count': 2, 'emoji': 'a'}]},
        {'sender_id': 1, 'reactions': None},
        {'sender_id': None, 'reactions': [{'count': 3, 'emoji': 'b'}]},
    ]
    st = cluster_stats(members)
    assert st['msgs'] == 3
    assert st['authors'] == 1   # None not counted, duplicate id=1 collapsed
    assert st['likes'] == 5


def test_chain_cluster_stats():
    """Documents (build_chains contract): msgs counts SUBSTANTIVE only,
    likes/authors run over ALL messages — reactions contribute."""
    long_msg = {'sender_id': 1, 'reactions': [{'count': 2, 'emoji': 'a'}]}
    react_1 = {'sender_id': 2, 'reactions': [{'count': 7, 'emoji': 'b'}]}
    react_2 = {'sender_id': None, 'reactions': None}
    doc_a = {
        'messages': [long_msg, react_1, react_2],
        'substantive': [long_msg],
    }
    other = {'sender_id': 2, 'reactions': []}
    doc_b = {
        'messages': [other],
        'substantive': [other],
    }
    st = chain_cluster_stats([doc_a, doc_b])
    assert st['msgs'] == 2       # substantive only — reactions NOT counted
    assert st['likes'] == 9      # 2 (long) + 7 (reaction's likes DO count)
    assert st['authors'] == 2    # senders 1 and 2; None not counted


def test_chain_cluster_stats_empty_reactions_and_missing_keys():
    doc = {
        'messages': [{'sender_id': 5}],   # no 'reactions' key at all
        'substantive': [{'sender_id': 5}],
    }
    st = chain_cluster_stats([doc])
    assert st == {'msgs': 1, 'likes': 0, 'authors': 1}


def test_score_full_and_zero():
    stats = {'msgs': 10, 'likes': 5, 'authors': 3}
    # maxes equal to the values → every signal normalizes to 1.0 → score == 1.0
    assert abs(score(stats, stats) - 1.0) < 1e-9
    # all-zero maxes → 0.0, no ZeroDivisionError
    assert score(stats, {'msgs': 0, 'likes': 0, 'authors': 0}) == 0.0
