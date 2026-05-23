"""
Clustering: UMAP + HDBSCAN over fragment embeddings (topic clouds).

Ported from ayda. NOT part of the MVP digest smoke — it's the second feature.
hdbscan/umap are heavy optional deps (requirements-clustering.txt); they are
imported lazily inside run_clustering so this module imports without them.
"""

import os
import logging
from collections import Counter

from core.llm.client import complete
from core.store.fragments_db import (
    get_all_embedded_fragments,
    get_latest_cluster_version,
    save_cluster_results,
)

logger = logging.getLogger(__name__)

UMAP_N_COMPONENTS = 50
UMAP_N_NEIGHBORS = 15
UMAP_RANDOM_STATE = 42

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "prompts")


def run_clustering(min_cluster_size: int = 5, min_samples: int = 3) -> dict:
    """UMAP dim-reduction + HDBSCAN clustering of embeddings. Saves a new version.

    Requires hdbscan + umap-learn (requirements-clustering.txt).
    """
    import numpy as np
    import hdbscan
    import umap

    fragments = get_all_embedded_fragments()
    if not fragments:
        return {'version': 0, 'n_clusters': 0, 'n_noise': 0, 'n_total': 0, 'clusters': []}

    n_total = len(fragments)
    logger.info("Clustering %d fragments (min_cluster_size=%d, min_samples=%d)",
                n_total, min_cluster_size, min_samples)

    ids = [f['id'] for f in fragments]
    matrix = np.array([f['embedding'] for f in fragments])

    logger.info("UMAP reducing %d → %d dims", matrix.shape[1], UMAP_N_COMPONENTS)
    reducer = umap.UMAP(
        n_components=UMAP_N_COMPONENTS, metric='cosine',
        n_neighbors=UMAP_N_NEIGHBORS, min_dist=0.0, random_state=UMAP_RANDOM_STATE,
    )
    reduced = reducer.fit_transform(matrix)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size, min_samples=min_samples,
        metric='euclidean', cluster_selection_method='eom',
    )
    labels = clusterer.fit_predict(reduced)

    cluster_map: dict[int, list[int]] = {}
    n_noise = 0
    for idx, label in enumerate(labels):
        if label == -1:
            n_noise += 1
            continue
        cluster_map.setdefault(label, []).append(idx)

    n_clusters = len(cluster_map)
    logger.info("HDBSCAN: %d clusters, %d noise", n_clusters, n_noise)

    version = (get_latest_cluster_version() or 0) + 1
    clusters_data = []
    for label, indices in sorted(cluster_map.items()):
        fragment_ids = [ids[i] for i in indices]
        cluster_fragments = [fragments[i] for i in indices]
        clusters_data.append({
            'label': int(label),
            'size': len(fragment_ids),
            'preview': _make_preview(cluster_fragments),
            'fragment_ids': fragment_ids,
        })
    clusters_data.sort(key=lambda c: c['size'], reverse=True)

    try:
        names = generate_cluster_names(clusters_data, fragments)
        for cd in clusters_data:
            cd['name'] = names.get(cd['label'], '')
    except Exception as e:
        logger.warning("Failed to generate AI names: %s", e)
        for cd in clusters_data:
            cd['name'] = ''

    save_cluster_results(version, clusters_data)
    logger.info("Saved clustering v%d: %d clusters", version, n_clusters)

    return {
        'version': version, 'n_clusters': n_clusters, 'n_noise': n_noise,
        'n_total': n_total,
        'clusters': [
            {'label': c['label'], 'size': c['size'], 'preview': c['preview'],
             'name': c.get('name', '')}
            for c in clusters_data[:20]
        ],
    }


def _make_preview(cluster_fragments: list[dict]) -> str:
    """Cluster preview: most common tag + first 2 fragment texts."""
    all_tags = []
    for f in cluster_fragments:
        all_tags.extend(f.get('tags') or [])
    top_tag = Counter(all_tags).most_common(1)[0][0] if all_tags else ""

    sorted_frags = sorted(cluster_fragments, key=lambda f: f['created_at'])
    texts = []
    for f in sorted_frags[:2]:
        t = f['text'][:80].replace('\n', ' ').strip()
        if len(f['text']) > 80:
            t += "..."
        texts.append(t)

    preview = " | ".join(texts)
    if top_tag:
        preview = f"{top_tag}: {preview}"
    return preview


def generate_cluster_names(clusters_data: list[dict], all_fragments: list[dict]) -> dict[int, str]:
    """Short AI names for clusters via core.llm.client.complete."""
    frag_by_id = {f['id']: f for f in all_fragments}
    with open(os.path.join(_PROMPTS_DIR, "cluster_name.md"), encoding="utf-8") as fh:
        template = fh.read()

    names: dict[int, str] = {}
    logger.info("Generating AI names for %d clusters...", len(clusters_data))

    for i, cd in enumerate(clusters_data):
        frags = sorted(
            [frag_by_id[fid] for fid in cd['fragment_ids'] if fid in frag_by_id],
            key=lambda f: f['created_at'],
        )
        if not frags:
            continue

        step = max(1, len(frags) // 5)
        samples = [frags[j] for j in range(0, len(frags), step)][:5]
        sample_texts = "\n---\n".join(
            f"{' '.join(f.get('tags') or [])} {f['text'][:200]}" for f in samples
        )
        prompt = template.format(sample_texts=sample_texts)

        try:
            names[cd['label']] = complete(prompt, temperature=0.3, max_tokens=30)
        except Exception as e:
            logger.warning("AI name error for cluster %s: %s", cd['label'], e)
            names[cd['label']] = ''

        if (i + 1) % 10 == 0:
            logger.info("  Named %d/%d clusters", i + 1, len(clusters_data))

    logger.info("Generated %d AI names", sum(1 for v in names.values() if v))
    return names
