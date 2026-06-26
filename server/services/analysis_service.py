from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from ..config import NOISY_ANALYSIS_FIELDS
from ..schemas import AnalyzeSelectionRequest
from .path_service import resolve_chroma_path


def load_selected_documents(request: AnalyzeSelectionRequest, selected_ids: list[str]) -> dict[str, str]:
    if not selected_ids:
        return {}
    path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
    if not validation["valid"]:
        return {}
    try:
        collection = chromadb.PersistentClient(path=str(path)).get_collection(request.collection_name)
        result = collection.get(ids=selected_ids, include=["documents"])
    except Exception:
        return {}
    ids = [str(item) for item in result.get("ids", [])]
    documents = result.get("documents") or []
    return {
        doc_id: str(documents[index] or "")
        for index, doc_id in enumerate(ids)
        if index < len(documents)
    }


def keyword_summary(selected_texts: list[str], background_texts: list[str], limit: int = 16) -> list[dict[str, Any]]:
    selected = [text for text in selected_texts if text.strip()]
    background = [text for text in background_texts if text.strip()]
    if not selected:
        return []
    try:
        documents = selected + background
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=350,
            token_pattern=r"(?u)\b[A-Za-z][A-Za-z'-]{3,}\b",
        )
        matrix = vectorizer.fit_transform(documents)
        terms = vectorizer.get_feature_names_out()
        selected_scores = np.asarray(matrix[: len(selected)].mean(axis=0)).ravel()
        if background:
            background_scores = np.asarray(matrix[len(selected) :].mean(axis=0)).ravel()
        else:
            background_scores = np.zeros_like(selected_scores)
        distinctiveness = selected_scores - (background_scores * 0.65)
        order = np.argsort(distinctiveness)[::-1]
        results = []
        for index in order:
            if not useful_analysis_term(str(terms[index])):
                continue
            if selected_scores[index] <= 0:
                continue
            results.append(
                {
                    "term": str(terms[index]),
                    "score": round(float(selected_scores[index]), 4),
                    "distinctiveness": round(float(distinctiveness[index]), 4),
                }
            )
            if len(results) >= limit:
                break
        return results
    except Exception:
        words: list[str] = []
        for text in selected:
            words.extend([word.lower() for word in text.split() if useful_analysis_term(word)])
        return [{"term": term, "score": count, "distinctiveness": count} for term, count in Counter(words).most_common(limit)]


def metadata_commonality(selected_rows: list[dict[str, Any]], all_rows: list[dict[str, Any]], limit: int = 18) -> list[dict[str, Any]]:
    fields = sorted(
        {
            key
            for row in selected_rows
            for key in row.keys()
            if key.startswith("meta.")
        }
    )
    fields = [field for field in fields if useful_analysis_field(field)]
    candidates: list[dict[str, Any]] = []
    for field in fields:
        selected_counts = Counter(clean_value(row.get(field)) for row in selected_rows if clean_value(row.get(field)))
        all_counts = Counter(clean_value(row.get(field)) for row in all_rows if clean_value(row.get(field)))
        for value, count in selected_counts.most_common(4):
            total = all_counts.get(value, count)
            selected_pct = count / max(1, len(selected_rows))
            global_pct = total / max(1, len(all_rows))
            lift = selected_pct / max(global_pct, 0.0001)
            if count < 2 and len(selected_rows) > 2:
                continue
            candidates.append(
                {
                    "field": field.removeprefix("meta."),
                    "value": value,
                    "selected_count": count,
                    "selected_percent": round(selected_pct * 100, 1),
                    "global_percent": round(global_pct * 100, 1),
                    "lift": round(lift, 2),
                }
            )
    return sorted(candidates, key=lambda item: (item["lift"], item["selected_count"]), reverse=True)[:limit]


def value_distribution(
    selected_rows: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    field: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    selected_counts = Counter(
        clean_value(row.get(field))
        for row in selected_rows
        if clean_value(row.get(field)) and useful_distribution_value(clean_value(row.get(field)))
    )
    all_counts = Counter(
        clean_value(row.get(field))
        for row in all_rows
        if clean_value(row.get(field)) and useful_distribution_value(clean_value(row.get(field)))
    )
    results = []
    for value, count in selected_counts.most_common(limit):
        results.append(
            {
                "value": value,
                "selected_count": count,
                "selected_percent": round((count / max(1, len(selected_rows))) * 100, 1),
                "global_count": all_counts.get(value, 0),
            }
        )
    return results


def date_ranges(selected_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    fields = sorted(
        {
            key
            for row in selected_rows
            for key in row.keys()
            if ("date" in key.lower() or "time" in key.lower())
            and not isinstance(row.get(key), dict)
            and useful_analysis_field(key)
        }
    )
    ranges = []
    for field in fields:
        values = [row.get(field) for row in selected_rows if row.get(field) not in (None, "")]
        if not values:
            continue
        parsed = pd.to_datetime(pd.Series(values).astype(str), errors="coerce", format="mixed")
        parsed = parsed.dropna()
        if parsed.empty:
            continue
        ranges.append(
            {
                "field": field.removeprefix("meta."),
                "start": parsed.min().date().isoformat(),
                "end": parsed.max().date().isoformat(),
                "count": str(len(parsed)),
            }
        )
    return ranges[:8]


def representative_rows(selected_rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.get("id", "")),
            "source": str(row.get("source", "")),
            "title": str(row.get("title", "")),
            "cluster": str(row.get("cluster", "")),
            "topic_label": str(row.get("topic_label", "")),
            "preview": str(row.get("preview", "")),
        }
        for row in selected_rows[:limit]
    ]


def clean_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value)


def normalized_field_name(field: str) -> str:
    return field.removeprefix("meta.").lower()


def useful_analysis_field(field: str) -> bool:
    name = normalized_field_name(field)
    if name in NOISY_ANALYSIS_FIELDS:
        return False
    if name.endswith("_id") or name.endswith("id"):
        return False
    if name.endswith("_ids") or name.endswith("_count") or name.endswith("_scope"):
        return False
    if name.endswith("_compact"):
        return False
    if "time" in name and name not in {"air_time", "publish_time"}:
        return False
    return True


def useful_distribution_value(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower().strip()
    if lowered in {"unknown", "untitled", "none", "nan"}:
        return False
    if len(lowered) < 3:
        return False
    return True


def useful_analysis_term(value: str) -> bool:
    lowered = value.lower().strip()
    if not lowered:
        return False
    tokens = lowered.split()
    filler = {
        "like",
        "just",
        "going",
        "think",
        "thing",
        "things",
        "right",
        "yeah",
        "okay",
        "episode",
        "podcast",
        "host",
        "guest",
        "speaker",
    }
    if any(token in filler for token in tokens):
        return False
    if any(len(token) < 4 for token in tokens):
        return False
    return True
