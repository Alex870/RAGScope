from __future__ import annotations

import json
import logging
import pickle
import re
import sqlite3
import urllib.error
import urllib.request
import uuid
from collections import Counter
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)

from clustering import cluster_embeddings, nearest_neighbors
from persistence import SAVED_VIEWS_DIR, ensure_saved_views_dir, list_views, load_view, rename_view, save_view
from reducers import reduce_embeddings
from state import WorkspaceState
from server.schemas import (
    AnalyzeSelectionRequest,
    BrowseFolderRequest,
    CollectionRequest,
    DatasetRequest,
    DocumentRequest,
    LlmAuditInterpretRequest,
    LlmModelsRequest,
    LlmQueryGenerationRequest,
    RenameViewRequest,
    RetrievalExperimentRequest,
    SaveViewRequest,
    SearchRequest,
)
from topics import label_topics
from visualization import categorical_color_map
from sklearn.feature_extraction.text import TfidfVectorizer

CACHE_VERSION = "analysis-topic-filter-v4"
DEFAULT_SEMANTIC_EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
NOISY_ANALYSIS_FIELDS = {
    "id",
    "row_index",
    "parent_id",
    "node_id",
    "chunk_id",
    "document_id",
    "source_id",
    "start_time",
    "end_time",
    "start",
    "end",
    "duration",
    "segment_count",
    "child_ids",
    "speaker_scope",
    "source",
    "source_file",
    "source_type",
    "title",
    "episode_title",
    "level",
    "node_type",
    "timestamp",
    "created_at",
    "updated_at",
    "episode_date",
    "episode_sort_key",
    "date",
    "year",
    "month",
    "day",
    "speaker",
    "speakers",
    "host",
    "guest",
}

app = FastAPI(title="RAGScope API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_DIR = Path(".cache")
PROJECTION_CACHE_DIR = CACHE_DIR / "projections"
DATASET_RESPONSE_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
DATASET_RESPONSE_CACHE_LIMIT = 8


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/collections")
def collections(request: CollectionRequest) -> dict[str, Any]:
    requested_path = Path(request.chroma_path).expanduser()
    path, validation = resolve_chroma_path(requested_path)
    if not validation["valid"]:
        return {"collections": [], "validation": validation, **validation}
    try:
        client = chromadb.PersistentClient(path=str(path))
        names = [item if isinstance(item, str) else item.name for item in client.list_collections()]
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        names = read_collection_names_from_sqlite(path)
        if names:
            return {
                "collections": sorted(names),
                "validation": validation,
                "resolved_path": str(path),
                "warning": f"ChromaDB client inspection failed, but collections were recovered from chroma.sqlite3: {message}",
                **validation,
            }
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not read ChromaDB at {path}: {message}. "
                "Confirm the folder contains an accessible chroma.sqlite3 file and is not locked by another process."
            ),
        ) from exc
    return {"collections": sorted(names), "validation": validation, "resolved_path": str(path), **validation}


@app.post("/api/browse-folder")
def browse_folder(request: BrowseFolderRequest) -> dict[str, Any]:
    start_path = Path(request.start_path or ".").expanduser()
    if not start_path.exists():
        start_path = Path.cwd()
    if start_path.is_file():
        start_path = start_path.parent
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            title="Select ChromaDB folder",
            initialdir=str(start_path.resolve()),
            mustexist=True,
        )
        root.destroy()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Folder picker could not be opened: {exc}") from exc
    if not selected:
        return {"selected_path": ""}
    resolved_path, validation = resolve_chroma_path(Path(selected).expanduser())
    return {
        "selected_path": selected,
        "resolved_path": str(resolved_path),
        "validation": validation,
        **validation,
    }


@app.post("/api/dataset")
def dataset(request: DatasetRequest) -> dict[str, Any]:
    if not request.collection_name:
        raise HTTPException(status_code=400, detail="A collection must be selected.")
    path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["message"])

    signature = collection_signature(path, request.collection_name)
    cache_key = dataset_cache_key(path, request, signature)
    cached = memory_cache_get(cache_key)
    if cached is not None:
        return cached

    frame, embeddings = load_collection_frame(path, request.collection_name, request.max_load_size)
    if frame.empty:
        response = empty_dataset_response(validation)
        memory_cache_set(cache_key, response)
        return response
    if embeddings is None or len(embeddings) != len(frame):
        frame["x"] = 0.0
        frame["y"] = 0.0
        frame["z"] = 0.0
        frame["cluster"] = "missing_embeddings"
        frame["topic_label"] = "Missing embeddings"
        topics: dict[str, dict[str, Any]] = {}
        clusterer = "missing"
    else:
        dimensions = 3 if request.chart_view == "3D" else 2
        projection = load_or_compute_projection(cache_key, frame, embeddings, request, dimensions)
        coords = projection["coords"]
        frame["x"] = coords["x"].values
        frame["y"] = coords["y"].values
        if "z" in coords:
            frame["z"] = coords["z"].values
        labels = projection["labels"]
        clusterer = projection["clusterer"]
        frame["cluster"] = labels
        frame["topic_label"] = projection["topic_labels"]
        topics = projection["topics"]

    color_map = categorical_color_map(frame["cluster"].fillna("").astype(str).tolist())
    frame.insert(0, "cluster_color", frame["cluster"].astype(str).map(color_map).fillna(""))
    rows = dataframe_records(frame.drop(columns=["document"], errors="ignore"))
    response = {
        "rows": rows,
        "topics": topic_records(topics),
        "cluster_color_map": color_map,
        "metadata_fields": metadata_fields(frame),
        "metrics": {
            "loaded": len(frame),
            "clusters": len(set(frame["cluster"].astype(str))),
            "embedding_dim": int(embeddings.shape[1]) if embeddings is not None and embeddings.ndim == 2 else None,
            "clusterer": clusterer,
        },
        "validation": validation,
        "cache": {"memory": False, "projection": True},
    }
    memory_cache_set(cache_key, response)
    return response


@app.post("/api/document")
def document(request: DocumentRequest) -> dict[str, Any]:
    if not request.collection_name:
        raise HTTPException(status_code=400, detail="A collection must be selected.")
    path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["message"])
    try:
        collection = chromadb.PersistentClient(path=str(path)).get_collection(request.collection_name)
        result = collection.get(ids=[request.id], include=["documents", "metadatas"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Document lookup failed: {exc}") from exc
    ids = result.get("ids") or []
    if not ids:
        raise HTTPException(status_code=404, detail="Document not found")
    documents = result.get("documents") or [""]
    metadatas = result.get("metadatas") or [{}]
    return {
        "id": str(ids[0]),
        "document": str(documents[0] or ""),
        "metadata": metadatas[0] if isinstance(metadatas[0], dict) else {},
    }


@app.post("/api/analyze-selection")
def analyze_selection(request: AnalyzeSelectionRequest) -> dict[str, Any]:
    selected_ids = [str(item) for item in request.selected_ids if str(item).strip()]
    if not selected_ids:
        raise HTTPException(status_code=400, detail="Select one or more points or rows before analyzing.")
    dataset_response = dataset(DatasetRequest(**request.model_dump(exclude={"selected_ids"})))
    rows = dataset_response.get("rows") or []
    if not rows:
        raise HTTPException(status_code=400, detail="No dataset rows are available for analysis.")

    selected_set = set(selected_ids)
    selected_rows = [row for row in rows if str(row.get("id")) in selected_set]
    if not selected_rows:
        raise HTTPException(status_code=404, detail="Selected ids were not found in the loaded dataset.")

    selected_docs = load_selected_documents(request, selected_ids[:200])
    selected_texts = [
        selected_docs.get(str(row.get("id")), "") or str(row.get("preview") or "")
        for row in selected_rows[:500]
    ]
    background_texts = [str(row.get("preview") or "") for row in rows if str(row.get("id")) not in selected_set][:1000]

    return {
        "selected_count": len(selected_rows),
        "total_count": len(rows),
        "coverage_percent": round((len(selected_rows) / max(1, len(rows))) * 100, 2),
        "keywords": keyword_summary(selected_texts, background_texts),
        "common_metadata": metadata_commonality(selected_rows, rows),
        "dominant_clusters": value_distribution(selected_rows, rows, "cluster", limit=12),
        "dominant_topics": value_distribution(selected_rows, rows, "topic_label", limit=12),
        "source_distribution": value_distribution(selected_rows, rows, "source", limit=12),
        "date_ranges": date_ranges(selected_rows),
        "representative_chunks": representative_rows(selected_rows),
    }


@app.post("/api/semantic-search")
def semantic_search(request: SearchRequest) -> dict[str, Any]:
    if not request.collection_name:
        raise HTTPException(status_code=400, detail="A collection must be selected.")
    if not request.query.strip():
        return {"ids": []}
    try:
        path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
        if not validation["valid"]:
            raise ValueError(validation["message"])
        collection = chromadb.PersistentClient(path=str(path)).get_collection(request.collection_name)
        expected_dim = collection_embedding_dim(collection)
        query_embedding = embed_semantic_query(request.query)
        actual_dim = len(query_embedding)
        if expected_dim is not None and actual_dim != expected_dim:
            raise ValueError(
                f"Semantic search embedding dimension mismatch. "
                f"Collection expects {expected_dim} dimensions, but "
                f"{DEFAULT_SEMANTIC_EMBEDDING_MODEL} produced {actual_dim}. "
                "Use the same embedding model that created this ChromaDB collection."
            )
        candidate_ids = unique_strings(request.candidate_ids)
        if candidate_ids:
            result_ids = semantic_search_candidate_ids(collection, query_embedding, candidate_ids, request.top_k)
            return {
                "ids": result_ids,
                "embedding_model": DEFAULT_SEMANTIC_EMBEDDING_MODEL,
                "embedding_dim": len(query_embedding),
                "searched_candidate_count": len(candidate_ids),
            }
        result = collection.query(query_embeddings=[query_embedding], n_results=max(1, request.top_k))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Semantic search failed: {exc}") from exc
    ids = result.get("ids") or [[]]
    return {
        "ids": [str(item) for item in ids[0]],
        "embedding_model": DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        "embedding_dim": len(query_embedding),
    }


@app.post("/api/retrieval-experiment")
def retrieval_experiment(request: RetrievalExperimentRequest) -> dict[str, Any]:
    if not request.collection_name:
        raise HTTPException(status_code=400, detail="A collection must be selected.")
    if not request.query.strip():
        return {"ids": [], "results": [], "histogram": [], "scores": []}
    try:
        path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
        if not validation["valid"]:
            raise ValueError(validation["message"])
        collection = chromadb.PersistentClient(path=str(path)).get_collection(request.collection_name)
        expected_dim = collection_embedding_dim(collection)
        query_embedding = embed_semantic_query(request.query)
        actual_dim = len(query_embedding)
        if expected_dim is not None and actual_dim != expected_dim:
            raise ValueError(
                f"Retrieval experiment embedding dimension mismatch. "
                f"Collection expects {expected_dim} dimensions, but "
                f"{DEFAULT_SEMANTIC_EMBEDDING_MODEL} produced {actual_dim}. "
                "Use the same embedding model that created this ChromaDB collection."
            )
        scored = score_candidate_documents(
            collection=collection,
            query_embedding=query_embedding,
            candidate_ids=unique_strings(request.candidate_ids),
            top_k=request.top_k,
            histogram_bins=request.histogram_bins,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Retrieval experiment failed: {exc}") from exc

    return {
        **scored,
        "query": request.query,
        "mode": request.mode,
        "embedding_model": DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        "embedding_dim": len(query_embedding),
    }


@app.post("/api/llm/generate-audit-queries")
def generate_audit_queries(request: LlmQueryGenerationRequest) -> dict[str, Any]:
    if request.provider.provider == "Disabled":
        return {"queries": request.existing_queries[: request.query_count], "raw": ""}
    prompt = {
        "collection": request.collection_name,
        "existing_queries": request.existing_queries,
        "sample_chunks": request.sample_chunks[:24],
        "instructions": (
            "Generate diverse benchmark queries for evaluating a podcast RAG vector database. "
            "Cover factual retrieval, broad themes, speaker viewpoint, hierarchy summaries, and edge cases. "
            "Return strict JSON only: {\"queries\":[\"...\"]}."
        ),
    }
    raw = llm_chat_completion(
        request.provider,
        [
            {"role": "system", "content": "You generate concise RAG benchmark queries and return strict JSON."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.35,
    )
    parsed = parse_json_object(raw)
    queries = [str(item).strip() for item in parsed.get("queries", []) if str(item).strip()]
    return {"queries": queries[: request.query_count], "raw": raw}


@app.post("/api/llm/models")
def llm_models(request: LlmModelsRequest) -> dict[str, Any]:
    if request.provider.provider == "Disabled":
        return {"models": []}
    base_url = str(request.provider.base_url or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="LLM base URL is required.")
    headers = {"Content-Type": "application/json"}
    api_key = str(request.provider.api_key or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    api_request = urllib.request.Request(f"{base_url}/models", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(api_request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=400, detail=f"Model lookup failed: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Model lookup failed: {exc}") from exc
    models = []
    model_details: dict[str, Any] = {}
    for item in body.get("data", []):
        if isinstance(item, dict) and item.get("id"):
            model_id = str(item["id"])
            models.append(model_id)
            model_details[model_id] = {
                "context_length": extract_context_length(item),
                "raw": item,
            }
        elif isinstance(item, str):
            models.append(item)
            model_details[item] = {"context_length": None, "raw": item}
    return {"models": sorted(set(models)), "model_details": model_details}


@app.post("/api/llm/interpret-audit")
def interpret_audit(request: LlmAuditInterpretRequest) -> dict[str, Any]:
    if request.provider.provider == "Disabled":
        return {"enabled": False}
    compact_report = deepcopy(request.audit_report)
    compact_report.pop("raw", None)
    compact_report = shrink_for_llm(compact_report)
    prompt = {
        "audit_report": compact_report,
        "contexts": shrink_for_llm(request.contexts[:12]),
        "context_policy": "limited metadata/previews only" if request.limit_context else "full retrieved chunk text allowed",
        "instructions": (
            "Interpret this deterministic RAG quality audit. Judge retrieval usefulness, explain likely root causes, "
            "and suggest concrete pipeline improvements. Return strict JSON with keys: summary, strengths, risks, "
            "recommended_actions, query_judgements. query_judgements should include query, rating_1_to_5, and note."
        ),
    }
    result = llm_chat_completion_result(
        request.provider,
        [
            {"role": "system", "content": "You are a careful RAG evaluation analyst. Return strict JSON only."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    raw = result["content"]
    parsed = parse_json_object(raw)
    parsed["enabled"] = True
    parsed["raw"] = raw
    parsed["diagnostics"] = llm_output_diagnostics(raw, parsed, result)
    return parsed


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def semantic_search_candidate_ids(collection: Any, query_embedding: list[float], candidate_ids: list[str], top_k: int) -> list[str]:
    scored = score_candidate_documents(collection, query_embedding, candidate_ids, top_k, histogram_bins=10)
    return [item["id"] for item in scored["results"]]


def score_candidate_documents(
    collection: Any,
    query_embedding: list[float],
    candidate_ids: list[str],
    top_k: int,
    histogram_bins: int = 20,
) -> dict[str, Any]:
    include = ["embeddings", "documents", "metadatas"]
    payload = collection.get(ids=candidate_ids, include=include) if candidate_ids else collection.get(include=include)
    ids = [str(item) for item in payload.get("ids", [])]
    embeddings_raw = payload.get("embeddings")
    if not ids or embeddings_raw is None:
        return {"ids": [], "results": [], "histogram": [], "scores": [], "candidate_count": 0}
    vectors = np.asarray(embeddings_raw, dtype=float)
    query = np.asarray(query_embedding, dtype=float)
    if vectors.ndim != 2 or query.ndim != 1 or vectors.shape[1] != query.shape[0]:
        raise ValueError(
            f"Semantic candidate search dimension mismatch. "
            f"Candidates have {vectors.shape[1] if vectors.ndim == 2 else 'unknown'} dimensions, "
            f"query has {query.shape[0]}."
        )
    vector_norms = np.linalg.norm(vectors, axis=1)
    query_norm = np.linalg.norm(query)
    denominator = np.maximum(vector_norms * query_norm, 1e-12)
    scores = vectors.dot(query) / denominator
    order = np.argsort(scores)[::-1]
    top_order = order[: max(1, top_k)]
    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []
    results: list[dict[str, Any]] = []
    for rank, index in enumerate(top_order, start=1):
        row_id = ids[int(index)]
        metadata = metadatas[int(index)] if int(index) < len(metadatas) and isinstance(metadatas[int(index)], dict) else {}
        document = documents[int(index)] if int(index) < len(documents) else ""
        results.append(
            {
                "id": row_id,
                "rank": rank,
                "score": round(float(scores[int(index)]), 6),
                "preview": str(document or "")[:280],
                "metadata": metadata,
                "source": metadata.get("source") or metadata.get("source_file") or "",
                "title": metadata.get("title") or metadata.get("episode_title") or "",
                "level": metadata.get("level") or metadata.get("node_type") or "",
            }
        )
    return {
        "ids": [item["id"] for item in results],
        "results": results,
        "histogram": score_histogram(scores, histogram_bins),
        "scores": [round(float(score), 6) for score in scores.tolist()],
        "candidate_count": len(ids),
    }


def score_histogram(scores: np.ndarray, bins: int) -> list[dict[str, Any]]:
    if scores.size == 0:
        return []
    if float(np.min(scores)) == float(np.max(scores)):
        return [{"start": round(float(scores[0]), 6), "end": round(float(scores[0]), 6), "count": int(scores.size)}]
    counts, edges = np.histogram(scores, bins=bins)
    return [
        {
            "start": round(float(edges[index]), 6),
            "end": round(float(edges[index + 1]), 6),
            "count": int(count),
        }
        for index, count in enumerate(counts)
    ]


def llm_chat_completion(provider: Any, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    return llm_chat_completion_result(provider, messages, temperature)["content"]


def llm_chat_completion_result(provider: Any, messages: list[dict[str, str]], temperature: float = 0.2) -> dict[str, Any]:
    base_url = str(provider.base_url or "").strip().rstrip("/")
    model = str(provider.model or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="LLM base URL is required.")
    if not model:
        raise HTTPException(status_code=400, detail="LLM model is required.")
    url = f"{base_url}/chat/completions"
    current_messages = messages
    base_payload = {
        "model": model,
        "messages": current_messages,
        "temperature": temperature,
        "max_tokens": 1400,
    }
    headers = {"Content-Type": "application/json"}
    api_key = str(provider.api_key or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    context_retry = False
    detected_context_window: int | None = None
    while True:
        attempts = [
            {**base_payload, "response_format": {"type": "json_object"}},
            {
                **base_payload,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "rag_audit_json",
                        "schema": {"type": "object", "additionalProperties": True},
                    },
                },
            },
            {**base_payload, "response_format": {"type": "text"}},
            base_payload,
        ]
        last_error = ""
        retry_with_smaller_context = False
        for payload in attempts:
            try:
                body = openai_compatible_chat_request(url, payload, headers)
                choices = body.get("choices") or []
                first_choice = choices[0] if choices else {}
                content = first_choice.get("message", {}).get("content", "") if first_choice else ""
                if content:
                    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
                    return {
                        "content": str(content),
                        "finish_reason": first_choice.get("finish_reason"),
                        "usage": usage,
                        "context_retry": context_retry,
                        "context_window": detected_context_window,
                    }
                last_error = "LLM returned no content."
            except urllib.error.HTTPError as exc:
                last_error = exc.read().decode("utf-8", errors="replace")
                context_window = parse_context_window_error(last_error)
                if context_window and not context_retry:
                    detected_context_window = context_window
                    context_retry = True
                    retry_with_smaller_context = True
                    current_messages = shrink_messages_for_context(current_messages, context_window)
                    base_payload = {
                        **base_payload,
                        "messages": current_messages,
                        "max_tokens": min(700, max(256, context_window // 8)),
                    }
                    break
                if "response_format" not in last_error and "json_schema" not in last_error and "json_object" not in last_error:
                    break
            except Exception as exc:
                last_error = str(exc)
                break
        if retry_with_smaller_context:
            continue
        raise HTTPException(status_code=400, detail=f"LLM request failed: {last_error}")


def openai_compatible_chat_request(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}


def extract_context_length(model_info: Any) -> int | None:
    if not isinstance(model_info, dict):
        return None
    candidate_keys = {
        "context_length",
        "max_context_length",
        "n_ctx",
        "ctx_size",
        "context_window",
        "max_position_embeddings",
        "max_sequence_length",
    }

    def walk(value: Any) -> int | None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key).lower()
                if key_text in candidate_keys or ("context" in key_text and ("length" in key_text or "window" in key_text)):
                    parsed = coerce_positive_int(item)
                    if parsed:
                        return parsed
                found = walk(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        return None

    return walk(model_info)


def coerce_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def llm_output_diagnostics(raw: str, parsed: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    finish_reason = result.get("finish_reason")
    usage = result.get("usage") or {}
    if finish_reason == "length":
        warnings.append("The LLM stopped because it reached the response token limit. The interpretation may be truncated or degraded.")
    if not parsed:
        warnings.append("The LLM did not return parseable JSON.")
    elif not parsed.get("summary") and not parsed.get("recommended_actions"):
        warnings.append("The LLM returned JSON, but it did not contain the expected audit interpretation fields.")
    if looks_degenerate(raw):
        warnings.append("The LLM output appears repetitive or corrupted. Try a lower temperature, a larger context window, the Limit setting, or a different model.")
    if result.get("context_retry"):
        warnings.append("The first LLM request exceeded the model context window, so the app retried with a smaller prompt.")
    return {
        "warnings": warnings,
        "finish_reason": finish_reason,
        "usage": usage,
        "context_retry": result.get("context_retry", False),
        "context_window": result.get("context_window"),
    }


def looks_degenerate(text: str) -> bool:
    if not text:
        return False
    repeated_words = re.findall(r"([\w'\uAC00-\uD7AF]{3,})(?:\W+\1){8,}", text, flags=re.IGNORECASE)
    if repeated_words:
        return True
    compact = re.sub(r"\s+", "", text)
    for size in (4, 6, 8, 12):
        chunks = [compact[index : index + size] for index in range(0, min(len(compact), 2400), size)]
        if chunks:
            most_common = Counter(chunks).most_common(1)[0][1]
            if most_common >= 18:
                return True
    return False


def parse_context_window_error(text: str) -> int | None:
    match = re.search(r"n_ctx:\s*(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def shrink_messages_for_context(messages: list[dict[str, str]], context_window: int) -> list[dict[str, str]]:
    # Rough local-model heuristic: keep prompt chars comfortably under token window.
    total_budget = max(1800, context_window * 2)
    system_messages = [message for message in messages if message.get("role") == "system"]
    user_messages = [message for message in messages if message.get("role") != "system"]
    system_budget = min(900, total_budget // 4)
    remaining_budget = total_budget - system_budget
    compact: list[dict[str, str]] = []
    for message in system_messages[:1]:
        compact.append({**message, "content": short_backend(message.get("content", ""), system_budget)})
    per_user_budget = max(900, remaining_budget // max(1, len(user_messages)))
    for message in user_messages:
        compact.append({**message, "content": short_backend(message.get("content", ""), per_user_budget)})
    return compact


def shrink_for_llm(value: Any, max_string: int = 900, max_list: int = 12, depth: int = 0) -> Any:
    if depth > 6:
        return short_backend(value, 240)
    if isinstance(value, str):
        return short_backend(value, max_string)
    if isinstance(value, list):
        return [shrink_for_llm(item, max_string, max_list, depth + 1) for item in value[:max_list]]
    if isinstance(value, dict):
        return {str(key): shrink_for_llm(item, max_string, max_list, depth + 1) for key, item in list(value.items())[:40]}
    return value


def short_backend(value: Any, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit - 1]}..."


@lru_cache(maxsize=2)
def get_semantic_embedding_model(model_name: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Semantic search requires sentence-transformers. "
            "Run the launcher or install requirements.txt to add it."
        ) from exc
    return SentenceTransformer(model_name)


def embed_semantic_query(query: str) -> list[float]:
    model = get_semantic_embedding_model()
    encoded = model.encode(
        [f"{BGE_QUERY_PREFIX}{query.strip()}"],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    vector = np.asarray(encoded[0], dtype=float)
    return vector.tolist()


def collection_embedding_dim(collection: Any) -> int | None:
    try:
        sample = collection.get(limit=1, include=["embeddings"])
    except Exception:
        return None
    embeddings = sample.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        return None
    vector = np.asarray(embeddings[0], dtype=float)
    if vector.ndim == 0:
        return None
    return int(vector.shape[0])


@app.post("/api/neighbors")
def neighbors(request: DatasetRequest, row_index: int, top_k: int = 8) -> dict[str, Any]:
    path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["message"])
    frame, embeddings = load_collection_frame(path, request.collection_name, request.max_load_size)
    if embeddings is None:
        return {"rows": []}
    indices = nearest_neighbors(embeddings, row_index, top_k)
    neighbors_frame = frame[frame["row_index"].isin(indices)][["id", "source", "title", "preview"]]
    return {"rows": dataframe_records(neighbors_frame)}


@app.get("/api/views")
def saved_views() -> dict[str, Any]:
    ensure_saved_views_dir()
    views = []
    for path in list_views():
        try:
            state = load_view(path)
        except Exception:
            continue
        views.append(
            {
                "filename": path.name,
                "file": path.name,
                "path": str(path),
                "id": state.id,
                "name": state.name,
                "description": state.description,
                "timestamp": state.timestamp,
                "collection_name": state.collection_name,
                "state": state.to_dict(),
            }
        )
    return {"views": views}


@app.post("/api/views")
def save_workspace(request: SaveViewRequest) -> dict[str, Any]:
    payload = react_state_to_workspace(request.state)
    payload["name"] = request.name or payload.get("name") or "Untitled View"
    payload["description"] = request.description or payload.get("description") or ""
    state = WorkspaceState.from_dict(payload)
    if not state.id:
        state.id = str(uuid.uuid4())
    path = save_view(state)
    return {"filename": path.name, "file": path.name, "path": str(path), "state": state.to_dict()}


@app.delete("/api/views/{filename}")
def delete_workspace(filename: str) -> dict[str, str]:
    path = (SAVED_VIEWS_DIR / filename).resolve()
    root = ensure_saved_views_dir().resolve()
    if path.parent != root or not path.exists():
        raise HTTPException(status_code=404, detail="Saved view not found")
    path.unlink()
    return {"status": "deleted"}


@app.put("/api/views/{filename}/rename")
def rename_workspace(filename: str, request: RenameViewRequest) -> dict[str, Any]:
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="A view name is required.")
    path = (SAVED_VIEWS_DIR / filename).resolve()
    root = ensure_saved_views_dir().resolve()
    if path.parent != root or not path.exists():
        raise HTTPException(status_code=404, detail="Saved view not found")
    new_path = rename_view(path, request.name.strip())
    state = load_view(new_path)
    return {
        "filename": new_path.name,
        "file": new_path.name,
        "path": str(new_path),
        "state": state.to_dict(),
    }


def resolve_chroma_path(path: Path) -> tuple[Path, dict[str, Any]]:
    validation = validate_chroma_path(path)
    if validation["valid"]:
        return path, validation
    child = path / "chroma"
    child_validation = validate_chroma_path(child)
    if child_validation["valid"]:
        return child, {
            **child_validation,
            "message": "Valid ChromaDB folder found in the chroma subfolder.",
            "requested_path": str(path),
        }
    return path, validation


def validate_chroma_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"valid": False, "message": "The folder does not exist."}
    if not path.is_dir():
        return {"valid": False, "message": "The path is not a folder."}
    try:
        has_contents = any(path.iterdir())
    except OSError as exc:
        return {"valid": False, "message": f"The folder could not be read: {exc}"}
    if not has_contents:
        return {"valid": False, "message": "The folder exists but is empty."}
    if not (path / "chroma.sqlite3").exists():
        return {"valid": False, "message": "No chroma.sqlite3 file was found in this folder."}
    return {"valid": True, "message": "Valid ChromaDB folder."}


def read_collection_names_from_sqlite(path: Path) -> list[str]:
    sqlite_path = path / "chroma.sqlite3"
    if not sqlite_path.exists():
        return []
    try:
        with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as connection:
            cursor = connection.execute("SELECT name FROM collections ORDER BY name")
            return [str(row[0]) for row in cursor.fetchall() if row and row[0]]
    except Exception:
        return []


def collection_signature(path: Path, collection_name: str) -> dict[str, Any]:
    sqlite_path = path / "chroma.sqlite3"
    try:
        count = chromadb.PersistentClient(path=str(path)).get_collection(collection_name).count()
    except Exception:
        count = None
    sqlite_stat = sqlite_path.stat()
    return {
        "path": str(path.resolve()),
        "sqlite_size": sqlite_stat.st_size,
        "collection": collection_name,
        "count": count,
    }


def dataset_cache_key(path: Path, request: DatasetRequest, signature: dict[str, Any]) -> str:
    payload = {
        "signature": signature,
        "cache_version": CACHE_VERSION,
        "max_load_size": request.max_load_size,
        "chart_view": request.chart_view,
        "reduction": asdict(request.reduction),
        "clustering": asdict(request.clustering),
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def memory_cache_get(key: str) -> dict[str, Any] | None:
    cached = DATASET_RESPONSE_CACHE.get(key)
    if cached is None:
        return None
    DATASET_RESPONSE_CACHE.move_to_end(key)
    response = deepcopy(cached)
    response["cache"] = {**response.get("cache", {}), "memory": True}
    return response


def memory_cache_set(key: str, response: dict[str, Any]) -> None:
    DATASET_RESPONSE_CACHE[key] = deepcopy(response)
    DATASET_RESPONSE_CACHE.move_to_end(key)
    while len(DATASET_RESPONSE_CACHE) > DATASET_RESPONSE_CACHE_LIMIT:
        DATASET_RESPONSE_CACHE.popitem(last=False)


def projection_cache_path(key: str) -> Path:
    PROJECTION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTION_CACHE_DIR / f"{key}.pickle"


def load_or_compute_projection(
    key: str,
    frame: pd.DataFrame,
    embeddings: np.ndarray,
    request: DatasetRequest,
    dimensions: int,
) -> dict[str, Any]:
    path = projection_cache_path(key)
    if path.exists():
        try:
            with path.open("rb") as handle:
                return pickle.load(handle)
        except Exception:
            path.unlink(missing_ok=True)

    coords = reduce_embeddings(embeddings, request.reduction, dimensions)
    labels, clusterer = cluster_embeddings(embeddings, request.clustering)
    labeled_frame = frame.copy()
    labeled_frame["cluster"] = labels
    labeled_frame, topics = label_topics(labeled_frame, embeddings)
    payload = {
        "coords": coords,
        "labels": labels,
        "clusterer": clusterer,
        "topic_labels": labeled_frame["topic_label"].tolist(),
        "topics": topics,
    }
    try:
        with path.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass
    return payload


def react_state_to_workspace(payload: dict[str, Any]) -> dict[str, Any]:
    sidebar = payload.get("sidebar") or {}
    reduction = {
        "method": sidebar.get("reductionMethod", "UMAP"),
        "n_neighbors": sidebar.get("neighbors", 15),
        "min_dist": sidebar.get("minDist", 0.1),
        "use_sampling": sidebar.get("sampling", True),
        "sample_size": sidebar.get("maxLoad", payload.get("max_load_size", 10000)),
    }
    clustering = {
        "method": sidebar.get("clusteringMethod", "Auto"),
        "kmeans_clusters": sidebar.get("clusterCount", 8),
        "hdbscan_min_cluster_size": sidebar.get("minClusterSize", 8),
    }
    return {
        **payload,
        "chroma_path": payload.get("chroma_path", "./chroma"),
        "collection_name": payload.get("collection_name", ""),
        "max_load_size": sidebar.get("maxLoad", payload.get("max_load_size", 10000)),
        "chart_view": "3D" if int(sidebar.get("dimensions", 2) or 2) == 3 else "2D",
        "reduction": reduction,
        "clustering": clustering,
        "color_mode": sidebar.get("colorMode", "cluster"),
        "text_search_query": sidebar.get("textSearch", ""),
        "semantic_search_query": sidebar.get("semanticSearch", ""),
        "semantic_top_k": sidebar.get("semanticTopK", 10),
        "selected_ids": payload.get("selected_points", payload.get("selected_ids", [])),
        "highlighted_ids": payload.get("highlighted_ids", []),
        "highlighted_neighbors": payload.get("highlighted_neighbors", []),
        "plot_view": payload.get("plot_relayout", payload.get("plot_view", {})),
        "popup_delay_seconds": sidebar.get("popupDelay", 1.0),
        "popups_enabled": sidebar.get("hoverEnabled", True),
        "table_height": payload.get("table_height", 280),
        "sidebar_settings": sidebar,
    }


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
        "speaker",
        "guest",
        "people",
        "make",
        "good",
        "bad",
        "basically",
        "stuff",
        "need",
        "years",
        "months",
        "fucking",
        "fuck",
        "shit",
    }
    months = {
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
    if any(token in filler or token in months for token in tokens):
        return False
    if any("'" in token for token in tokens):
        return False
    if any(token.isdigit() for token in tokens):
        return False
    if any(any(char.isdigit() for char in token) for token in tokens):
        return False
    return len(lowered) >= 4


def load_collection_frame(path: Path, collection_name: str, max_load_size: int) -> tuple[pd.DataFrame, np.ndarray | None]:
    collection = chromadb.PersistentClient(path=str(path)).get_collection(collection_name)
    count = collection.count()
    if count == 0:
        return pd.DataFrame(), None
    payload = collection.get(limit=min(count, max_load_size), include=["documents", "embeddings", "metadatas"])
    ids = [str(item) for item in payload.get("ids", [])]
    documents = payload.get("documents") or [""] * len(ids)
    metadatas = payload.get("metadatas") or [{} for _ in ids]
    embeddings_raw = payload.get("embeddings")
    embeddings = np.asarray(embeddings_raw, dtype=float) if embeddings_raw is not None else None
    rows: list[dict[str, Any]] = []
    for index, doc_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        text = str(documents[index] if index < len(documents) else "")
        row: dict[str, Any] = {
            "row_index": index,
            "id": doc_id,
            "document": text,
            "preview": preview(text),
            "source": str(first_present(metadata, ["source", "source_file", "file", "path"])),
            "title": str(first_present(metadata, ["title", "episode_title", "document_title"])),
            "metadata": metadata,
        }
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                row[f"meta.{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows), embeddings


def empty_dataset_response(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": [],
        "topics": {},
        "cluster_color_map": {},
        "metadata_fields": [],
        "metrics": {"loaded": 0, "clusters": 0, "embedding_dim": None, "clusterer": None},
        "validation": validation,
    }


def topic_records(topics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for cluster, payload in topics.items():
        records.append({"cluster": str(cluster), **payload})
    return sorted(records, key=lambda item: str(item.get("cluster", "")))


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records"))


def metadata_fields(frame: pd.DataFrame) -> list[dict[str, str]]:
    fields = []
    for column in sorted([item for item in frame.columns if item.startswith("meta.")]):
        series = frame[column].dropna()
        kind = "categorical"
        if pd.api.types.is_numeric_dtype(series):
            kind = "numeric"
        elif is_date_like(series):
            kind = "date"
        fields.append({"name": column, "label": column.removeprefix("meta."), "kind": kind})
    return fields


def is_date_like(values: pd.Series) -> bool:
    if values.empty or pd.api.types.is_numeric_dtype(values):
        return False
    try:
        parsed = pd.to_datetime(values.astype(str).head(25), errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(values.astype(str).head(25), errors="coerce")
    return bool(parsed.notna().mean() > 0.8)


def first_present(metadata: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return ""


def preview(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "..."
