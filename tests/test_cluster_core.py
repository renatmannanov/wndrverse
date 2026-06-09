"""Unit test for the pure clustering core (core.brain.clustering.cluster_embeddings).

Two clearly separated clouds of 1536-dim vectors → ≥1 cluster, label/probability
lengths match the input. No DB, no LLM. Requires hdbscan + umap (clustering deps).
"""

import numpy as np

from core.brain.clustering import cluster_embeddings


def test_two_clouds_give_at_least_one_cluster():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.01, (6, 1536)) + 1.0
    b = rng.normal(0, 0.01, (6, 1536)) - 1.0
    vecs = np.vstack([a, b]).tolist()

    labels, probs = cluster_embeddings(vecs, min_cluster_size=3)

    assert len(labels) == 12
    assert len(probs) == 12
    n_clusters = len({l for l in labels if l != -1})
    assert n_clusters >= 1
    # labels are in {-1, 0, 1, ...}
    assert all(l == -1 or l >= 0 for l in labels)
    # probabilities in [0, 1]
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_tiny_input_does_not_crash():
    # fewer points than min_cluster_size → all noise, no error
    vecs = [[0.1] * 1536, [0.2] * 1536]
    labels, probs = cluster_embeddings(vecs, min_cluster_size=3)
    assert labels == [-1, -1]
    assert probs == [0.0, 0.0]
