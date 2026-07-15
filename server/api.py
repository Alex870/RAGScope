from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import uuid
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import DEFAULT_SEMANTIC_EMBEDDING_MODEL
from .chroma_loader import inspect_provenance, trace_provenance
from .persistence import SAVED_VIEWS_DIR, ensure_saved_views_dir, list_views, load_view, rename_view, save_view
from .schemas import (
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
from .services.analysis_service import (
    date_ranges,
    keyword_summary,
    load_selected_documents,
    metadata_commonality,
    representative_rows,
    value_distribution,
)
from .services.cache_service import dataset_cache_key, load_or_compute_projection, memory_cache_get, memory_cache_set
from .services.frame_service import dataframe_records, empty_dataset_response, load_collection_frame, metadata_fields, topic_records
from .services.llm_service import (
    extract_context_length,
    llm_chat_completion,
    llm_chat_completion_result,
    llm_output_diagnostics,
    parse_json_object,
    shrink_for_llm,
)
from .services.path_service import collection_signature, read_collection_names_from_sqlite, resolve_chroma_path
from .services.search_service import (
    collection_embedding_dim,
    embed_semantic_query,
    score_candidate_documents,
    semantic_search_candidate_ids,
    unique_strings,
)
from .state import WorkspaceState
from .visualization import categorical_color_map
from .evaluation import (
    JudgedDataset,
    ExperimentManifest,
    ExperimentStore,
    IncompatibleComparisonError,
    aggregate_metric,
    compare_reports,
    create_queries_from_documents,
    evaluate_results,
    paired_bootstrap,
    promotion_decision,
    render_comparison_markdown,
    retrieval_metrics,
)
from .diagnostics import cluster_stability, embedding_quality, projection_diagnostics
from .explanations import create_counterfactual
from .state import ClusteringSettings, ReductionSettings


LOGGER = logging.getLogger(__name__)

app = FastAPI(title="RAGScope API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


BENCHMARK_LOCAL_DIR = Path("benchmarks/local")
EXPERIMENT_RUN_DIR = Path("benchmarks/runs")


@app.get("/api/evaluation/datasets")
def evaluation_datasets() -> dict[str, Any]:
    BENCHMARK_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    fixture_dir = Path("benchmarks/fixtures")
    paths = sorted(list(fixture_dir.glob("*-dataset.json")) + list(BENCHMARK_LOCAL_DIR.glob("*.json")))
    datasets = []
    for path in paths:
        try:
            dataset = JudgedDataset.load(path)
            datasets.append({"path": str(path), "dataset_id": dataset.dataset_id, "name": dataset.name, "queries": len(dataset.queries), "corpus_fingerprint": dataset.corpus_fingerprint, "judged_dataset_fingerprint": dataset.fingerprint, "format": dataset.pack_version})
        except Exception as exc:
            datasets.append({"path": str(path), "error": str(exc)})
    return {"datasets": datasets}


@app.post("/api/evaluation/datasets")
def save_evaluation_dataset(payload: dict[str, Any]) -> dict[str, Any]:
    BENCHMARK_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        source = payload.get("dataset") if payload.get("format") == "podcast-evaluation-pack-v1" else payload
        source = source or {}
        queries = []
        from .evaluation import EvidenceJudgment, JudgedQuery
        for item in source.get("queries", []):
            record = dict(item)
            judgments = [EvidenceJudgment(**value) for value in record.pop("judgments", [])]
            queries.append(JudgedQuery(judgments=judgments, **record))
        dataset = JudgedDataset(
            name=str(source.get("name") or "Untitled Benchmark"),
            corpus_fingerprint=str(source.get("corpus_fingerprint") or "unknown"),
            queries=queries,
            dataset_id=str(source.get("dataset_id") or uuid.uuid4()),
        )
        path = BENCHMARK_LOCAL_DIR / f"{dataset.dataset_id}.json"
        dataset.save(path)
        return {"saved": True, "format": "podcast-evaluation-pack-v1", "path": str(path), "dataset": dataset.as_dict(), "fingerprint": dataset.fingerprint}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid judged dataset: {exc}") from exc


@app.get("/api/evaluation/datasets/{dataset_id}")
def get_evaluation_dataset(dataset_id: str) -> dict[str, Any]:
    for path in list(Path("benchmarks/fixtures").glob("*-dataset.json")) + list(BENCHMARK_LOCAL_DIR.glob("*.json")):
        dataset = JudgedDataset.load(path)
        if dataset.dataset_id == dataset_id:
            return {"path": str(path), "dataset": dataset.as_dict()}
    raise HTTPException(status_code=404, detail="Judged dataset not found")


@app.post("/api/evaluation/validate-identities")
def validate_evaluation_identities(payload: dict[str, Any]) -> dict[str, Any]:
    available_documents = set(map(str, payload.get("available_document_ids") or []))
    available_spans = set(map(str, payload.get("available_source_span_ids") or []))
    stale_documents, stale_spans = [], []
    for query in payload.get("queries") or []:
        for judgment in query.get("judgments") or []:
            if available_documents and str(judgment.get("document_id")) not in available_documents:
                stale_documents.append(str(judgment.get("document_id")))
            if available_spans and str(judgment.get("source_span_id")) not in available_spans:
                stale_spans.append(str(judgment.get("source_span_id")))
    return {"stale_document_ids": sorted(set(stale_documents)), "stale_source_span_ids": sorted(set(stale_spans))}


@app.post("/api/evaluation/diagnostics")
def evaluation_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    embeddings = np.asarray(payload.get("embeddings") or [], dtype=float)
    if embeddings.ndim != 2 or not len(embeddings):
        raise HTTPException(status_code=400, detail="A non-empty 2D embeddings array is required")
    profile = str(payload.get("profile") or "interactive")
    result = {"profile": profile, "embedding_quality": embedding_quality(embeddings, payload.get("metadata") or []), "visualization_audit": {"deterministic_metrics": True, "llm_assisted_interpretation": False, "projection_semantics": "Projected proximity is not original-space similarity."}}
    if payload.get("project", True):
        result["projection"] = projection_diagnostics(embeddings, ReductionSettings(), sample_size=5000 if profile == "thorough" else 1000)
    if payload.get("cluster", True):
        result["cluster"] = cluster_stability(embeddings, ClusteringSettings(), runs=5)
    return result


@app.post("/api/evaluation/provenance")
def evaluation_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") or []
    result = inspect_provenance(str(payload.get("chroma_path") or "./chroma"), rows)
    if payload.get("document_id"):
        result["trace"] = trace_provenance(str(payload["document_id"]), rows)
    return result


@app.post("/api/evaluation/runs")
def save_evaluation_run(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        manifest = ExperimentManifest(**payload["manifest"])
        path = ExperimentStore(EXPERIMENT_RUN_DIR).save(manifest, payload.get("report") or {}, str(payload.get("notes") or ""))
        return {"run_id": manifest.run_id, "path": str(path)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/evaluation/runs/{run_id}/notes")
def update_evaluation_notes(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = ExperimentStore(EXPERIMENT_RUN_DIR).update_notes(run_id, str(payload.get("notes") or ""))
    return {"saved": True, "path": str(path)}


@app.post("/api/evaluation/counterfactual")
def evaluation_counterfactual(payload: dict[str, Any]) -> dict[str, Any]:
    run = create_counterfactual(str(payload.get("parent_run_id") or ""), dict(payload.get("changes") or {}))
    return {"run_id": run.run_id, "parent_run_id": run.parent_run_id, "changes": run.changes, "request": payload.get("rerun_request") or {}}


@app.post("/api/evaluation/run")
def run_evaluation(payload: dict[str, Any]) -> dict[str, Any]:
    dataset_path = Path(str(payload.get("dataset_path") or ""))
    try:
        dataset = JudgedDataset.load(dataset_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load benchmark: {exc}") from exc
    return evaluate_results(dataset, payload)


@app.post("/api/evaluation/compare")
def compare_evaluations(payload: dict[str, Any]) -> dict[str, Any]:
    baseline = payload.get("baseline") or {}
    candidate = payload.get("candidate") or {}
    try:
        comparison = compare_reports(baseline, candidate, samples=int(payload.get("bootstrap_samples") or 10_000), seed=int(payload.get("seed") or 42))
    except IncompatibleComparisonError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    comparison["markdown"] = render_comparison_markdown(comparison)
    return comparison


@app.post("/api/evaluation/queries-from-documents")
def evaluation_queries_from_documents(payload: dict[str, Any]) -> dict[str, Any]:
    provenance = str(payload.get("provenance") or "human")
    if provenance not in {"human", "generated"}:
        raise HTTPException(status_code=400, detail="provenance must be human or generated")
    queries = create_queries_from_documents(payload.get("documents") or [], payload.get("query_texts"), provenance=provenance)
    return {"queries": [asdict(query) for query in queries], "count": len(queries), "provenance": provenance}


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


@app.post("/api/neighbors")
def neighbors(request: DatasetRequest, row_index: int, top_k: int = 8) -> dict[str, Any]:
    path, validation = resolve_chroma_path(Path(request.chroma_path).expanduser())
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["message"])
    frame, embeddings = load_collection_frame(path, request.collection_name, request.max_load_size)
    if embeddings is None:
        return {"rows": []}
    from .clustering import nearest_neighbors

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


def react_state_to_workspace(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate the React client state into the backend's portable workspace shape."""
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
