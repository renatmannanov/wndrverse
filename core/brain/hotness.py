"""
Hotness: pure functions for ranking hot topics. No DB, no LLM.

Reaction parsing + a normalized hotness score. Tested in isolation
(tests/test_hotness.py). Used by core.brain.topics to rank clusters.
"""

# weights fixed (rule #1: one path, no per-run "tunability" in the prototype).
# The rank is secondary — we don't polish the formula.
W_MSGS = 0.5
W_LIKES = 0.3
W_AUTHORS = 0.2


def likes_of(reactions: list[dict] | None) -> int:
    """Sum of `count` over all reactions of a message. None/[] → 0.

    reactions = [{'count': int, 'emoji': str}, ...]. Custom emoji sometimes arrive
    as a numeric id instead of a symbol — the count is still valid, so we sum all.
    Broken items (no 'count' / not an int) are skipped, not raised on.
    """
    if not reactions:
        return 0
    total = 0
    for r in reactions:
        if not isinstance(r, dict):
            continue
        c = r.get('count')
        if isinstance(c, int) and not isinstance(c, bool):
            total += c
    return total


def cluster_stats(members: list[dict]) -> dict:
    """Aggregates of a cluster from its fragments.

    members — fragments of one cluster (get_embedded_fragments_for_period format).
    Returns {'msgs': int, 'likes': int, 'authors': int} where:
      msgs    = len(members)
      likes   = sum(likes_of(m['reactions']))
      authors = number of UNIQUE sender_id (None authors are NOT counted — an
                anonymous author shouldn't inflate reach). distinct by sender_id,
                not by author_name.
    """
    msgs = len(members)
    likes = sum(likes_of(m.get('reactions')) for m in members)
    authors = len({m.get('sender_id') for m in members if m.get('sender_id') is not None})
    return {'msgs': msgs, 'likes': likes, 'authors': authors}


def score(stats: dict, maxes: dict) -> float:
    """Normalized hotness score within a set of clusters.

    maxes = {'msgs','likes','authors'} — maxima over ALL clusters of the set.
    Each signal is normalized x/max (max==0 → contribution 0, no div-by-zero).
    score = W_MSGS*msgs_n + W_LIKES*likes_n + W_AUTHORS*authors_n. Range [0,1].
    """
    def norm(key: str) -> float:
        m = maxes.get(key, 0)
        return stats.get(key, 0) / m if m else 0.0

    return W_MSGS * norm('msgs') + W_LIKES * norm('likes') + W_AUTHORS * norm('authors')
