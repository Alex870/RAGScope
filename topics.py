from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


STOP_WORDS = {
    "able",
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "being",
    "between",
    "could",
    "did",
    "didn",
    "does",
    "doesn",
    "don",
    "every",
    "from",
    "have",
    "into",
    "more",
    "other",
    "people",
    "really",
    "some",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "with",
    "would",
    "yeah",
    "okay",
    "like",
    "just",
    "know",
    "going",
    "think",
    "thing",
    "things",
    "right",
    "said",
    "say",
    "says",
    "want",
    "make",
    "good",
    "bad",
    "basically",
    "stuff",
    "need",
    "years",
    "months",
    "theyre",
    "youre",
    "thats",
    "dont",
    "isnt",
    "arent",
    "wont",
    "cant",
    "fucking",
    "fuck",
    "shit",
    "people",
    "really",
    "actually",
    "maybe",
    "probably",
    "episode",
    "podcast",
    "host",
    "guest",
    "speaker",
    "jan",
    "january",
    "feb",
    "february",
    "mar",
    "march",
    "apr",
    "april",
    "may",
    "jun",
    "june",
    "jul",
    "july",
    "aug",
    "august",
    "sep",
    "sept",
    "september",
    "oct",
    "october",
    "nov",
    "november",
    "dec",
    "december",
}


def label_topics(frame: pd.DataFrame, embeddings: np.ndarray | None) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    if frame.empty or "cluster" not in frame:
        frame["topic_label"] = ""
        return frame, {}

    topic_labels: dict[str, str] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for cluster in sorted(frame["cluster"].dropna().astype(str).unique(), key=str):
        cluster_frame = frame[frame["cluster"].astype(str) == cluster]
        texts = cluster_frame["document"].fillna("").astype(str).tolist()
        keywords = extract_keywords(texts)
        label = ", ".join(keywords[:4]) if keywords else f"Cluster {cluster}"
        topic_labels[cluster] = label
        representative_ids = representative_chunks(cluster_frame, embeddings)
        summaries[cluster] = {
            "label": label,
            "count": int(len(cluster_frame)),
            "keywords": keywords,
            "representative_ids": representative_ids,
        }

    result = frame.copy()
    result["topic_label"] = result["cluster"].astype(str).map(topic_labels).fillna("")
    return result, summaries


def extract_keywords(texts: list[str], max_terms: int = 8) -> list[str]:
    usable = [text for text in texts if text.strip()]
    if not usable:
        return []
    try:
        vectorizer = TfidfVectorizer(
            stop_words=list(STOP_WORDS.union(TfidfVectorizer(stop_words="english").get_stop_words() or set())),
            ngram_range=(1, 2),
            max_features=160,
            token_pattern=r"(?u)\b[A-Za-z][A-Za-z'-]{3,}\b",
            min_df=1,
        )
        matrix = vectorizer.fit_transform(usable)
        scores = np.asarray(matrix.sum(axis=0)).ravel()
        terms = vectorizer.get_feature_names_out()
        order = np.argsort(scores)[::-1]
        keywords = [str(terms[index]) for index in order if useful_keyword(str(terms[index]))]
        return keywords[:max_terms]
    except Exception:
        words: list[str] = []
        for text in usable:
            words.extend(
                word
                for word in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text.lower())
                if word not in STOP_WORDS and useful_keyword(word)
            )
        return [word for word, _count in Counter(words).most_common(max_terms)]


def useful_keyword(value: str) -> bool:
    tokens = value.lower().split()
    if not tokens:
        return False
    if any(token in STOP_WORDS for token in tokens):
        return False
    if any("'" in token for token in tokens):
        return False
    if any(re.fullmatch(r"\d+", token) for token in tokens):
        return False
    if any(re.fullmatch(r"\d{2,4}", token) for token in tokens):
        return False
    if any(re.search(r"\d", token) for token in tokens):
        return False
    if len(" ".join(tokens)) < 4:
        return False
    return True


def representative_chunks(cluster_frame: pd.DataFrame, embeddings: np.ndarray | None, count: int = 3) -> list[str]:
    if embeddings is None or "row_index" not in cluster_frame:
        return cluster_frame["id"].astype(str).head(count).tolist()
    indices = cluster_frame["row_index"].astype(int).tolist()
    vectors = embeddings[indices]
    centroid = vectors.mean(axis=0)
    distances = np.linalg.norm(vectors - centroid, axis=1)
    order = np.argsort(distances)[:count]
    return [str(cluster_frame.iloc[int(index)]["id"]) for index in order]
