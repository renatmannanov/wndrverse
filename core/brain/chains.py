"""
Reply chains: group messages of a period into thread "documents" BEFORE
clustering. Pure module — no DB, no LLM, no Telegram (like hotness.py).

Two link kinds (union-find over fragment indices):
  1. reply: fragment.reply_to_msg_id == another fragment's msg_id (string
     compare; a parent outside the slice → link ignored).
  2. series: consecutive messages OF ONE sender_id (adjacency within the
     sender's own messages, not the global timeline) with a gap of
     <= series_gap_s seconds. Longread parts are posted back-to-back with no
     reply between them, and other authors interleave even within the same
     second (real case 2026-06-10: msg 14068 landed between longread parts
     14067/14069) — global-timeline adjacency would break such series.

Each connected component becomes a document clustered as ONE point — so
short reactions ("спасибо за лонгрид") ride along with their thread instead
of forming a vocabulary-cluster of their own.

PII: nothing new is read or returned — the same fragment dicts, grouped.
The flood-filter `_is_substantive` lives here (moved from topics.py, which
re-exports it; import direction is topics → chains only, never back).
"""

import re
from datetime import datetime

import numpy as np

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Series link: same author, gap <= 5 min (longread parts are posted in a row
# without reply; calibrated on the 14067/14069/14070 case, see PLAN.md "Факты").
SERIES_GAP_S = 300


def _is_substantive(text: str) -> bool:
    """Heuristic flood-filter: True if the text carries real content.

    Drops low-information messages: fewer than 3 unique words, or mostly
    emoji/punctuation (alphanumeric-char ratio < 0.3).
    """
    if not text:
        return False
    words = _WORD_RE.findall(text.lower())
    if len(set(words)) < 3:
        return False
    alnum = sum(1 for ch in text if ch.isalnum())
    if alnum / len(text) < 0.3:
        return False
    return True


def _find(parent: list[int], i: int) -> int:
    root = i
    while parent[root] != root:
        root = parent[root]
    while parent[i] != root:  # path compression
        parent[i], i = root, parent[i]
    return root


def _union(parent: list[int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def build_chains(
    fragments: list[dict],
    *,
    min_chars: int = 80,           # same value as in build_topics
    series_gap_s: int = SERIES_GAP_S,
) -> list[dict]:
    """Messages of a period → thread documents for clustering.

    Returns [{
      'messages':    list[dict],   # ALL chain members, sorted by created_at
      'substantive': list[dict],   # flood-filter survivors (subset of messages)
      'embedding':   list[float],  # length-weighted mean over substantive
      'root':        dict,         # messages[0] — thread start (the anchor)
    }, ...] sorted by root created_at.

    Documents with NO substantive message are dropped (that's flood; the old
    per-message build_topics dropped them too — no degradation). msg_id /
    reply_to_msg_id are read via .get() — synthetic test dicts lack them,
    which just means "no reply links", not an error.
    """
    if not fragments:
        return []

    # Sort by created_at once; ISO strings parse via fromisoformat for gaps.
    def _ts(f: dict):
        v = f.get('created_at')
        return datetime.fromisoformat(v) if isinstance(v, str) else v

    order = sorted(range(len(fragments)), key=lambda i: _ts(fragments[i]) or datetime.min)
    parent = list(range(len(fragments)))

    # 1. reply links (msg_id None → can't be a parent; self-reply ignored by union)
    by_msg_id = {
        f.get('msg_id'): i for i, f in enumerate(fragments)
        if f.get('msg_id') is not None
    }
    for i, f in enumerate(fragments):
        rid = f.get('reply_to_msg_id')
        if rid is not None and rid in by_msg_id:
            _union(parent, by_msg_id[rid], i)

    # 2. series links: consecutive messages of one sender, small gap. Adjacency
    #    is per-sender, NOT global-timeline: other authors interleave between
    #    longread parts (even same-second) and must not break the series.
    by_sender: dict = {}
    for i in order:
        s = fragments[i].get('sender_id')
        if s is not None:
            by_sender.setdefault(s, []).append(i)
    for idxs in by_sender.values():
        for prev, cur in zip(idxs, idxs[1:]):
            tp, tc = _ts(fragments[prev]), _ts(fragments[cur])
            if tp is None or tc is None:
                continue
            if (tc - tp).total_seconds() <= series_gap_s:
                _union(parent, prev, cur)

    # Components → documents (order index keeps members time-sorted)
    components: dict[int, list[dict]] = {}
    for i in order:
        components.setdefault(_find(parent, i), []).append(fragments[i])

    docs = []
    for messages in components.values():
        substantive = [
            m for m in messages
            if len(m.get('text') or '') >= min_chars and _is_substantive(m['text'])
        ]
        if not substantive:
            continue
        weights = [len(m['text']) for m in substantive]
        embedding = np.average(
            [m['embedding'] for m in substantive], axis=0, weights=weights,
        ).tolist()
        docs.append({
            'messages': messages,
            'substantive': substantive,
            'embedding': embedding,
            'root': messages[0],
        })

    docs.sort(key=lambda d: _ts(d['root']) or datetime.min)
    return docs
