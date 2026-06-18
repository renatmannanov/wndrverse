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
import json
import logging

from core.brain.clustering import cluster_embeddings
from core.brain import hotness
from core.llm.client import complete
# _is_substantive lives in chains.py now (re-exported here for existing
# importers/tests); import direction is topics → chains only, never back.
from core.brain.chains import build_chains, _is_substantive  # noqa: F401

logger = logging.getLogger(__name__)

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "prompts")

# Anchor pick: a member this tightly attached (HDBSCAN probability) is "core"
# enough to represent the cluster; below it we risk linking a vocabulary-stray.
ANCHOR_MIN_PROBABILITY = 0.9

# topic_label.md asks for a {name, intrigue} OBJECT, so this is its own tolerant
# parser — NOT synthesis._parse_json_array, whose fallback hunts for '['/']' and
# would never find a JSON object. Strip a possible ```json fence (same trick as
# _parse_json_array / the critic), then json.loads; on any failure the caller
# falls back to name="тема", intrigue="".
def _parse_label_obj(raw: str) -> dict:
    """Parse {"name": ..., "intrigue": ...} out of an LLM reply. Returns {} on
    any failure (non-JSON, truncated, not a dict) — the caller is fail-soft."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    s = s.strip()
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


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
    # Recalibrated 2026-06-10 for DOCUMENT clustering (reply chains): boltalka
    # May = 707 fragments → 114 docs. mcs=3 gave 7 topics but rank#1 was a
    # 38-doc mega-cluster gluing 3 unrelated conversations; mcs=2 gives 14
    # topics with those conversations separated (user decision 2026-06-10).
    # "2 docs" ≥ a substantive thread each — not 2 lone messages.
    min_cluster_size: int = 2,  # layer 2: HDBSCAN — a topic is ≥ N documents
    min_authors: int = 2,       # layer 3: a topic is ≥2 people, not a monologue
    min_probability: float = 0.05,  # layer 3: drop loosely-attached points
    limit: int | None = None,   # top-N topics; None = all that pass the filters
) -> list[dict]:
    """Messages of one topic → ranked hot topics.

    Returns [{name, intrigue, msgs, anchor_channel_id, anchor_external_id}, ...]
    sorted by descending hotness (hotness.score). `intrigue` is a one-line hook
    (may be "" on LLM/parse failure — render skips it then). PII: only texts go
    to OpenAI; names/sender_id stay here.
    """
    # --- Layer 1: glue reply chains/series into documents; the flood-filter
    # (min_chars + _is_substantive) lives inside build_chains now — a document
    # with no substantive message is dropped there, but reactions riding along
    # a substantive thread stay in 'messages' (their likes/authors count).
    docs = build_chains(fragments, min_chars=min_chars)
    logger.info("build_topics: %d fragments → %d docs after chains (min_chars=%d)",
                len(fragments), len(docs), min_chars)
    if len(docs) < min_cluster_size:
        return []

    # --- Layer 2: cluster documents (order preserved so labels[i] ↔ docs[i]) ---
    vectors = [d['embedding'] for d in docs]
    labels, probs = cluster_embeddings(vectors, min_cluster_size=min_cluster_size)

    # Group docs by label, skipping noise (-1) AND loosely-attached points
    # (probs[i] < min_probability) — layer 3, applied HERE so loose docs don't
    # reach chain_cluster_stats and inflate msgs/likes. Each member carries its
    # HDBSCAN probability (copy, not mutation) so the anchor pick below can
    # prefer tightly-attached documents.
    clusters: dict[int, list[dict]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        if probs[i] < min_probability:
            continue
        clusters.setdefault(label, []).append({**docs[i], 'probability': probs[i]})

    # --- Layer 3: collect clusters, drop monologues (< min_authors) ---
    built = []
    for label, members in clusters.items():
        stats = hotness.chain_cluster_stats(members)
        if stats['authors'] < min_authors:
            continue
        # Anchor: earliest TIGHTLY-attached DOCUMENT (prob >= threshold), falling
        # back to plain earliest; the anchor message is that document's root —
        # the thread start. Same logic as the per-message anchor fix (ab6af26,
        # calibrated 2026-06-10): the earliest member overall is often a
        # vocabulary-stray glued to the cluster's edge, and anchoring there
        # sends the t.me link to an unrelated message.
        tight = [d for d in members if d['probability'] >= ANCHOR_MIN_PROBABILITY]
        anchor_doc = min(tight or members, key=lambda d: d['root']['created_at'])
        built.append({
            'members': members,
            'stats': stats,
            'anchor_channel_id': anchor_doc['root']['channel_id'],
            'anchor_external_id': anchor_doc['root']['external_id'],
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
        # Documents have no 'text' — sample over the flattened substantive
        # messages of all the cluster's chains (same even-step scheme as before).
        flat = sorted(
            (m for d in c['members'] for m in d['substantive']),
            key=lambda m: m['created_at'],
        )
        step = max(1, len(flat) // 5)
        samples = [flat[j] for j in range(0, len(flat), step)][:5]
        # PII: ONLY message text goes into the prompt — never sender_id/author_name/etc.
        sample_texts = "\n---\n".join(f['text'] for f in samples)
        prompt = template.format(sample_texts=sample_texts)
        # One call returns BOTH name and intrigue as a JSON object. max_tokens=200
        # (not 30/120): a Cyrillic intrigue ~140 chars ≈ 70-90 tokens + name + JSON
        # syntax would clip below 200 → truncated JSON → silent fail-soft.
        # Model is COMPLETION_MODEL (gpt-4o-mini, the cheap default in llm.client) —
        # ~200 tokens × N topics per call; mind the prod TPM ceiling (see progress).
        name, intrigue = "", ""
        try:
            raw = complete(prompt, temperature=0.3, max_tokens=200)
            obj = _parse_label_obj(raw)
            name = (obj.get('name') or "").strip()
            intrigue = (obj.get('intrigue') or "").strip()
        except Exception as e:
            logger.warning("topic-label LLM error: %s", e)
        result.append({
            'name': name or "тема",
            'intrigue': intrigue,
            'msgs': c['stats']['msgs'],
            'anchor_channel_id': c['anchor_channel_id'],
            'anchor_external_id': c['anchor_external_id'],
        })

    return result
