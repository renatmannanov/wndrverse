"""
Hot-topics orchestrator: messages of ONE topic → ranked hot topics.

This is the brain of the feature. It returns a STRUCTURE (list[TopicCluster]),
NOT text — rendering lives in delivery.topics_render. Here lives the cluster
QUALITY: 3 filtering layers (input flood-filter → HDBSCAN noise → output authors
+ probability). See task_tracker/.../hot-topics-digest for the design.

PII: only message TEXTS are sent to OpenAI (topic names). sender_id / author_name
never leave this module.
"""

import os
import re
import logging

from core.brain.clustering import cluster_embeddings
from core.brain import hotness
from core.llm.client import complete

logger = logging.getLogger(__name__)

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "prompts")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


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


def build_topics(
    fragments: list[dict],
    *,
    # Defaults calibrated 2026-06-09 on boltalka (step 7) over 1w/1m/all slices:
    # they give clean, distinct, flood-free topics on 1m (12 topics) and all
    # (no theme-merging). A 1-week slice yields few/zero topics — that's an
    # accepted limit of a narrow period, not a bug (too little data after the
    # flood-filter). min_chars=80 + _is_substantive cut short chatter; min_authors=2
    # drops monologues; min_probability=0.05 trims loosely-attached points.
    min_chars: int = 80,        # layer 1: input filter for short/flood
    min_cluster_size: int = 3,  # layer 2: HDBSCAN — a topic is ≥ N messages
    min_authors: int = 2,       # layer 3: a topic is ≥2 people, not a monologue
    min_probability: float = 0.05,  # layer 3: drop loosely-attached points
    limit: int | None = None,   # top-N topics; None = all that pass the filters
) -> list[dict]:
    """Messages of one topic → ranked hot topics.

    Returns [{name, msgs, anchor_channel_id, anchor_external_id}, ...] sorted by
    descending hotness (hotness.score). PII: only texts go to OpenAI; names/
    sender_id stay here.
    """
    # --- Layer 1: drop junk BEFORE clustering ---
    kept = [
        f for f in fragments
        if len(f.get('text') or '') >= min_chars and _is_substantive(f['text'])
    ]
    logger.info("build_topics: %d fragments → %d after flood-filter (min_chars=%d)",
                len(fragments), len(kept), min_chars)
    if len(kept) < min_cluster_size:
        return []

    # --- Layer 2: cluster (order of `kept` is preserved so labels[i] ↔ kept[i]) ---
    vectors = [f['embedding'] for f in kept]
    labels, probs = cluster_embeddings(vectors, min_cluster_size=min_cluster_size)

    # Group kept by label, skipping noise (-1) AND loosely-attached points
    # (probs[i] < min_probability) — layer 3, applied HERE so loose points don't
    # reach cluster_stats and inflate msgs/likes.
    clusters: dict[int, list[dict]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        if probs[i] < min_probability:
            continue
        clusters.setdefault(label, []).append(kept[i])

    # --- Layer 3: collect clusters, drop monologues (< min_authors) ---
    built = []
    for label, members in clusters.items():
        stats = hotness.cluster_stats(members)
        if stats['authors'] < min_authors:
            continue
        anchor = min(members, key=lambda m: m['created_at'])  # first by time
        built.append({
            'members': members,
            'stats': stats,
            'anchor_channel_id': anchor['channel_id'],
            'anchor_external_id': anchor['external_id'],
        })

    if not built:
        return []

    # --- Ranking ---
    maxes = {
        'msgs': max(c['stats']['msgs'] for c in built),
        'likes': max(c['stats']['likes'] for c in built),
        'authors': max(c['stats']['authors'] for c in built),
    }
    for c in built:
        c['score'] = hotness.score(c['stats'], maxes)
    built.sort(key=lambda c: c['score'], reverse=True)
    if limit is not None:
        built = built[:limit]

    # --- LLM names (only after ranking, only for final clusters — save tokens) ---
    with open(os.path.join(_PROMPTS_DIR, "topic_label.md"), encoding="utf-8") as fh:
        template = fh.read()

    result = []
    for c in built:
        members = sorted(c['members'], key=lambda m: m['created_at'])
        step = max(1, len(members) // 5)
        samples = [members[j] for j in range(0, len(members), step)][:5]
        # PII: ONLY message text goes into the prompt — never sender_id/author_name/etc.
        sample_texts = "\n---\n".join(f['text'] for f in samples)
        prompt = template.format(sample_texts=sample_texts)
        try:
            name = complete(prompt, temperature=0.3, max_tokens=30).strip()
        except Exception as e:
            logger.warning("topic-name LLM error: %s", e)
            name = ""
        result.append({
            'name': name or "тема",
            'msgs': c['stats']['msgs'],
            'anchor_channel_id': c['anchor_channel_id'],
            'anchor_external_id': c['anchor_external_id'],
        })

    return result
