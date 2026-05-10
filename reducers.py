from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from state import ReductionSettings


def reduce_embeddings(embeddings: np.ndarray, settings: ReductionSettings, dimensions: int = 2) -> pd.DataFrame:
    dimensions = 3 if dimensions == 3 else 2
    columns = ["x", "y", "z"] if dimensions == 3 else ["x", "y"]
    if embeddings.size == 0:
        return pd.DataFrame(columns=columns)

    if embeddings.shape[0] == 1:
        payload = {"x": [0.0], "y": [0.0]}
        if dimensions == 3:
            payload["z"] = [0.0]
        return pd.DataFrame(payload)

    if settings.method == "UMAP":
        try:
            import umap

            reducer = umap.UMAP(
                n_components=dimensions,
                n_neighbors=min(settings.n_neighbors, max(2, embeddings.shape[0] - 1)),
                min_dist=settings.min_dist,
                metric=settings.metric,
                init="random",
                random_state=None,
                n_jobs=-1,
            )
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="n_jobs value.*")
                warnings.filterwarnings("ignore", message="Spectral initialisation failed.*")
                coords = reducer.fit_transform(embeddings)
            return pd.DataFrame(coords, columns=columns)
        except Exception:
            pass

    n_components = min(dimensions, embeddings.shape[0], embeddings.shape[1])
    coords = PCA(n_components=n_components, random_state=settings.pca_random_state).fit_transform(embeddings)
    if n_components == 1:
        coords = np.column_stack([coords[:, 0], np.zeros(len(coords))])
    if dimensions == 3 and coords.shape[1] == 2:
        coords = np.column_stack([coords[:, 0], coords[:, 1], np.zeros(len(coords))])
    return pd.DataFrame(coords, columns=columns)
