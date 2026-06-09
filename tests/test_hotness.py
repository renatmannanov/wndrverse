"""Unit tests for core.brain.hotness — pure reaction/score functions, no DB/LLM."""

from core.brain.hotness import likes_of, cluster_stats, score


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


def test_score_full_and_zero():
    stats = {'msgs': 10, 'likes': 5, 'authors': 3}
    # maxes equal to the values → every signal normalizes to 1.0 → score == 1.0
    assert abs(score(stats, stats) - 1.0) < 1e-9
    # all-zero maxes → 0.0, no ZeroDivisionError
    assert score(stats, {'msgs': 0, 'likes': 0, 'authors': 0}) == 0.0
