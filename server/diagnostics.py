from __future__ import annotations

import time
from collections import Counter
from typing import Any

import numpy as np
from sklearn.manifold import trustworthiness
from sklearn.metrics import adjusted_mutual_info_score, silhouette_score

from .clustering import cluster_embeddings
from .reducers import reduce_embeddings
from .state import ClusteringSettings, ReductionSettings


def _neighbor_sets(values: np.ndarray, k: int) -> list[set[int]]:
    distances = np.linalg.norm(values[:, None, :] - values[None, :, :], axis=2)
    return [set(np.argsort(row)[1 : k + 1].tolist()) for row in distances]


def neighbor_preservation(original: np.ndarray, projected: np.ndarray, k: int = 15) -> float:
    if len(original) < 3:
        return 1.0
    k = min(k, len(original) - 1)
    source = _neighbor_sets(original, k)
    target = _neighbor_sets(projected, k)
    return float(np.mean([len(left.intersection(right)) / k for left, right in zip(source, target)]))


def projection_diagnostics(embeddings: np.ndarray, settings: ReductionSettings, seeds: list[int] | None = None, k: int = 15, sample_size: int = 5000) -> dict[str, Any]:
    started = time.perf_counter()
    seeds = seeds or [11, 23, 37, 53, 71]
    if len(embeddings) > sample_size:
        indices = np.random.default_rng(42).choice(len(embeddings), size=sample_size, replace=False)
        sample = embeddings[indices]
    else:
        sample = embeddings
    runs = []
    for seed in seeds:
        seeded = ReductionSettings(**{**settings.__dict__, "pca_random_state": seed, "random_state": seed})
        coords = reduce_embeddings(sample, seeded, 2).to_numpy()
        runs.append({"seed": seed, "coords": coords})
    first = runs[0]["coords"]
    preservation = neighbor_preservation(sample, first, k)
    stability = statistics_mean([neighbor_preservation(first, run["coords"], k) for run in runs[1:]]) if len(runs) > 1 else 1.0
    return {"k": k, "sample_size": len(sample), "seeds": seeds, "trustworthiness": float(trustworthiness(sample, first, n_neighbors=min(k, max(1, len(sample) // 2 - 1)))) if len(sample) > 5 else 1.0, "neighbor_preservation": preservation, "seed_stability": stability, "elapsed_seconds": time.perf_counter() - started}


def statistics_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def cluster_stability(embeddings: np.ndarray, settings: ClusteringSettings, runs: int = 5, sample_fraction: float = 0.8) -> dict[str, Any]:
    if len(embeddings) < 3:
        return {"runs": runs, "agreement": 1.0, "silhouette": None}
    rng = np.random.default_rng(42)
    label_maps = []
    sample_size = max(2, int(len(embeddings) * sample_fraction))
    for seed in range(runs):
        indices = np.sort(rng.choice(len(embeddings), size=sample_size, replace=False))
        configured = ClusteringSettings(**{**settings.__dict__, "random_state": 42 + seed})
        labels, algorithm = cluster_embeddings(embeddings[indices], configured)
        label_maps.append((indices, labels, algorithm))
    agreements = []
    for left, right in zip(label_maps, label_maps[1:]):
        common = sorted(set(left[0]).intersection(right[0]))
        if len(common) < 2:
            continue
        left_map = dict(zip(left[0], left[1]))
        right_map = dict(zip(right[0], right[1]))
        agreements.append(adjusted_mutual_info_score([left_map[index] for index in common], [right_map[index] for index in common]))
    full_labels, algorithm = cluster_embeddings(embeddings, settings)
    silhouette = None
    if len(set(full_labels)) > 1 and len(set(full_labels)) < len(embeddings):
        silhouette = float(silhouette_score(embeddings, full_labels))
    return {"runs": runs, "sample_fraction": sample_fraction, "agreement": statistics_mean(agreements), "silhouette": silhouette, "algorithm": algorithm}


def embedding_quality(embeddings: np.ndarray, metadata: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if embeddings.size == 0:
        return {}
    norms = np.linalg.norm(embeddings, axis=1)
    normalized = embeddings / np.maximum(norms[:, None], 1e-12)
    centroid = normalized.mean(axis=0)
    similarities = normalized @ normalized.T
    np.fill_diagonal(similarities, -1)
    hubs = np.argmax(similarities, axis=1)
    hub_counts = Counter(int(index) for index in hubs)
    coverage = {}
    for field in ("speaker", "episode_date", "node_type", "source"):
        values = [item.get(field) for item in (metadata or [])]
        coverage[field] = sum(value not in (None, "") for value in values) / max(1, len(values))
    return {"norm_min": float(norms.min()), "norm_mean": float(norms.mean()), "norm_max": float(norms.max()), "anisotropy": float(np.linalg.norm(centroid)), "max_hub_count": max(hub_counts.values(), default=0), "metadata_coverage": coverage}

