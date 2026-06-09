# Шаг 2: Чистое ядро кластеризации

> Зависит от: нет
> Статус: [ ] pending

## Задача

В `core/brain/clustering.py` ВЫНЕСТИ чистую функцию кластеризации, которая НЕ
ходит в БД и НЕ пишет версии — только числа на вход, метки на выход. Старый
`run_clustering()` ДОЛЖЕН продолжать работать (он становится обёрткой над ядром).

Новая функция:

```python
def cluster_embeddings(
    vectors: list[list[float]],
    *,
    min_cluster_size: int = 3,
    min_samples: int | None = None,
    umap_n_components: int = UMAP_N_COMPONENTS,
) -> tuple[list[int], list[float]]:
    """UMAP-reduce + HDBSCAN. Pure: vectors in, (labels, probabilities) out.

    labels[i] = cluster id of vectors[i], or -1 for noise.
    probabilities[i] = HDBSCAN cluster-membership strength [0..1] (0 for noise),
      used downstream to drop loosely-attached points.
    NO DB access, NO version write. Imports hdbscan/umap lazily (heavy deps).

    For SMALL slices (one topic/period — tens of vectors), the corpus-wide UMAP
    params are too aggressive; the caller passes a smaller min_cluster_size and may
    skip/shrink UMAP. If len(vectors) < umap_n_components, UMAP n_components is
    clamped to max(2, len(vectors)-1) so it doesn't error on tiny inputs.
    """
```

Рефактор:
1. Достать из текущего `run_clustering` блок UMAP+HDBSCAN (строки ~34–60) в
   `cluster_embeddings`. ВНИМАНИЕ: текущий код зовёт `clusterer.fit_predict(reduced)`
   — он возвращает ТОЛЬКО labels, а нам нужны ещё probabilities. Заменить на:
   `clusterer.fit(reduced)` затем взять `clusterer.labels_` и
   `clusterer.probabilities_`. Вернуть
   `(clusterer.labels_.tolist(), clusterer.probabilities_.tolist())`.
2. Клэмп для маленьких входов: `n_comp = min(umap_n_components, max(2, len(vectors)-1))`.
   Если `len(vectors) < min_cluster_size` → вернуть `([-1]*len(vectors), [0.0]*…)`
   (нечего кластеризовать).
3. `run_clustering` переписать так, чтобы он звал `cluster_embeddings` на
   `matrix` и дальше работал с метками как раньше (cluster_map, save). Поведение
   корпусной фичи НЕ меняется (те же дефолтные параметры). Метки теперь приходят
   из `cluster_embeddings` (labels-список), а не из `labels = clusterer.fit_predict`
   — итерируй по возвращённому списку labels как раньше.

ВАЖНО (правило #1 — один путь): для прототипа фиксируем движок HDBSCAN, НЕ
добавляем альтернативный агломеративный путь. Если на калибровке (шаг 7) HDBSCAN
не зайдёт — это отдельное решение, не сейчас.

## Тесты

- Юнит-тест `tests/test_cluster_core.py`: подать синтетические векторы (два явно
  разделённых облака по 5 точек в 1536-dim, например базовый вектор + шум) →
  ожидать ≥1 кластер, длины labels/probabilities == входу, метки в {-1, 0, 1,…}.
- Что может сломаться: `run_clustering` (корпусная фича). Проверить, что
  импортируется и сигнатура та же.

## Команды для верификации

```bash
# Ядро работает на маленьком входе без краша
python -c "
import numpy as np
from core.brain.clustering import cluster_embeddings
rng = np.random.default_rng(0)
a = rng.normal(0, 0.01, (6, 1536)) + 1.0
b = rng.normal(0, 0.01, (6, 1536)) - 1.0
vecs = np.vstack([a, b]).tolist()
labels, probs = cluster_embeddings(vecs, min_cluster_size=3)
print('labels:', labels)
print('n_clusters:', len({l for l in labels if l != -1}))
print('len ok:', len(labels)==12 and len(probs)==12)
"
# Корпусная фича не сломана
python -c "from core.brain.clustering import run_clustering; print('run_clustering import ok')"
# Юнит-тест
python -m pytest tests/test_cluster_core.py -q
```

## Критерии готовности

- [ ] `cluster_embeddings` возвращает `(labels, probabilities)` одинаковой длины
      со входом, на 2-х облаках даёт ≥1 кластер.
- [ ] Не падает на крошечном входе (< umap_n_components точек).
- [ ] `run_clustering` импортируется, сигнатура без изменений.
- [ ] `python -m pytest tests/test_cluster_core.py -q` зелёный.
