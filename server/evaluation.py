from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import statistics
import sys
import uuid
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DATASET_VERSION = "1.0"
EVALUATION_PACK_VERSION = "podcast-evaluation-pack-v1"
EXPERIMENT_VERSION = "1.0"
REPORT_VERSION = "1.0"
RELEVANCE = {0: "irrelevant", 1: "related", 2: "relevant_or_derived", 3: "primary_evidence"}
METRIC_KEYS = (
    "precision@10", "recall@20", "mrr", "ndcg@10", "hit_rate@10",
    "no_answer_false_positive_rate", "constraint_accuracy", "primary_coverage@10",
    "duplicate_hit_rate@10", "source_diversity@10", "latency_ms", "result_count",
)
QUALITY_METRICS = ("precision@10", "recall@20", "mrr", "ndcg@10", "hit_rate@10", "constraint_accuracy", "primary_coverage@10", "source_diversity@10")


class IncompatibleComparisonError(ValueError):
    """Raised when two evaluation artifacts are not from the same judged experiment."""


class ContractCompatibilityError(ValueError):
    pass


def require_compatible(encountered: str, supported: str, path: str | Path, component: str = "RAGScope") -> None:
    try:
        actual_major = int(str(encountered).split(".", 1)[0])
        supported_major = int(str(supported).split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid contract version in {path}: {encountered!r}") from exc
    if actual_major > supported_major:
        raise ContractCompatibilityError(
            f"{component} cannot read {path}: encountered contract {encountered}; maximum supported "
            f"contract is {supported}. Upgrade {component}."
        )


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceJudgment:
    document_id: str
    source_span_id: str
    grade: int
    reviewer: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.grade not in RELEVANCE:
            raise ValueError("Evidence grade must be between 0 and 3")


@dataclass
class JudgedQuery:
    query: str
    query_class: str
    answerable: bool
    judgments: list[EvidenceJudgment]
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    expected_speakers: list[str] = field(default_factory=list)
    expected_node_types: list[str] = field(default_factory=list)
    date_start: str = ""
    date_end: str = ""
    acceptable_evidence_sets: list[list[str]] = field(default_factory=list)
    reference_claims: list[str] = field(default_factory=list)
    hard_negative_ids: list[str] = field(default_factory=list)
    provenance: str = "human"
    human_reviewed: bool = True
    second_reviewer: str = ""
    adjudication_state: str = "accepted"
    adjudication_note: str = ""

    def __post_init__(self) -> None:
        if self.provenance not in {"human", "generated", "synthetic", "imported"}:
            raise ValueError("Query provenance must be human, generated, synthetic, or imported")
        if self.adjudication_state not in {"pending", "accepted", "rejected", "disputed"}:
            raise ValueError("Invalid adjudication state")


@dataclass
class JudgedDataset:
    name: str
    corpus_fingerprint: str
    queries: list[JudgedQuery]
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contract_version: str = DATASET_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pack_version: str = EVALUATION_PACK_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        return judged_dataset_fingerprint(self)

    def save(self, path: Path, *, pack: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.as_dict()
        if pack:
            payload = {"format": EVALUATION_PACK_VERSION, "dataset": payload}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def save_pack(self, path: Path) -> None:
        self.save(path, pack=True)

    @classmethod
    def load(cls, path: Path) -> "JudgedDataset":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") and payload.get("format") != EVALUATION_PACK_VERSION:
            raise ContractCompatibilityError(f"Unsupported evaluation pack format in {path}: {payload.get('format')}")
        if payload.get("format") == EVALUATION_PACK_VERSION:
            payload = payload.get("dataset") or {}
        require_compatible(payload.get("contract_version", "1.0"), DATASET_VERSION, path)
        queries = []
        for item in payload.get("queries", []):
            record = dict(item)
            judgments = [EvidenceJudgment(**value) for value in record.pop("judgments", [])]
            queries.append(JudgedQuery(judgments=judgments, **record))
        allowed = {"name", "corpus_fingerprint", "dataset_id", "contract_version", "created_at", "pack_version"}
        return cls(queries=queries, **{key: value for key, value in payload.items() if key in allowed})


@dataclass
class EpisodeReference:
    """Local-only episode identity; paths are references and content is never copied."""

    episode_id: str
    source_path: str
    source_sha256: str
    transcript_path: str = ""
    transcript_sha256: str = ""
    audio_ranges: list[dict[str, Any]] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    speaker_aliases: dict[str, list[str]] = field(default_factory=dict)
    glossary: list[str] = field(default_factory=list)
    protected_terms: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    duration_seconds: float | None = None
    notes: str = ""


@dataclass
class EvaluationPack:
    pack_id: str
    dataset: JudgedDataset
    episodes: list[EpisodeReference]
    reviewer: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    format: str = EVALUATION_PACK_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "pack_id": self.pack_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewer": self.reviewer,
            "episodes": [asdict(item) for item in self.episodes],
            "dataset": self.dataset.as_dict(),
        }

    @property
    def fingerprint(self) -> str:
        payload = self.as_dict()
        payload.pop("updated_at", None)
        return canonical_hash(payload)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "EvaluationPack":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format") != EVALUATION_PACK_VERSION:
            raise ContractCompatibilityError(f"Unsupported evaluation pack format in {path}: {payload.get('format')}")
        dataset_payload = dict(payload.get("dataset") or {})
        queries = []
        for item in dataset_payload.get("queries", []):
            record = dict(item)
            judgments = [EvidenceJudgment(**value) for value in record.pop("judgments", [])]
            queries.append(JudgedQuery(judgments=judgments, **record))
        allowed = {"name", "corpus_fingerprint", "dataset_id", "contract_version", "created_at", "pack_version"}
        dataset = JudgedDataset(queries=queries, **{key: value for key, value in dataset_payload.items() if key in allowed})
        return cls(
            pack_id=str(payload.get("pack_id") or path.stem), dataset=dataset,
            episodes=[EpisodeReference(**item) for item in payload.get("episodes", [])],
            reviewer=str(payload.get("reviewer") or ""),
            created_at=str(payload.get("created_at") or ""), updated_at=str(payload.get("updated_at") or ""),
        )

    def validate(
        self, base_path: Path, *, available_document_ids: Iterable[str] = (), available_source_span_ids: Iterable[str] = ()
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        document_ids = set(map(str, available_document_ids))
        span_ids = set(map(str, available_source_span_ids))
        episode_status = []
        for episode in self.episodes:
            status = {"episode_id": episode.episode_id, "source_ready": False, "transcript_ready": False}
            for kind, raw_path, expected_hash in (
                ("source", episode.source_path, episode.source_sha256),
                ("transcript", episode.transcript_path, episode.transcript_sha256),
            ):
                if not raw_path:
                    if kind == "source": errors.append(f"{episode.episode_id}: source_path is missing")
                    continue
                resolved = Path(raw_path)
                if not resolved.is_absolute(): resolved = base_path / resolved
                if not resolved.exists():
                    errors.append(f"{episode.episode_id}: {kind} path is missing: {resolved}")
                    continue
                actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if expected_hash and actual != expected_hash:
                    errors.append(f"{episode.episode_id}: {kind} hash changed: expected {expected_hash}, got {actual}")
                    continue
                status[f"{kind}_ready"] = True
            episode_status.append(status)
        incomplete = []
        stale_documents = []
        stale_spans = []
        for query in self.dataset.queries:
            if not query.human_reviewed or query.adjudication_state != "accepted": incomplete.append(query.query_id)
            if document_ids:
                stale_documents.extend(item.document_id for item in query.judgments if item.document_id not in document_ids)
            if span_ids:
                stale_spans.extend(item.source_span_id for item in query.judgments if item.source_span_id not in span_ids)
        if incomplete: warnings.append(f"Incomplete judgments: {', '.join(sorted(incomplete))}")
        if stale_documents: errors.append(f"Stale evidence IDs: {', '.join(sorted(set(stale_documents)))}")
        if stale_spans: errors.append(f"Stale source span IDs: {', '.join(sorted(set(stale_spans)))}")
        readiness = {
            "transcription": bool(self.episodes) and all(item["source_ready"] for item in episode_status),
            "retrieval": bool(self.dataset.queries) and not incomplete and not stale_documents and not stale_spans,
            "answer": bool(self.dataset.queries) and not incomplete and all(query.reference_claims or not query.answerable for query in self.dataset.queries),
        }
        return {"valid": not errors, "errors": errors, "warnings": warnings, "episodes": episode_status, "incomplete_query_ids": incomplete, "readiness": readiness, "pack_fingerprint": self.fingerprint}


@dataclass(frozen=True)
class NormalizedRunIdentity:
    schema_version: str
    corpus_fingerprint: str
    evaluation_pack_fingerprint: str
    source_commits: dict[str, str]
    model_identities: dict[str, Any]
    config_fingerprints: dict[str, str]
    hardware_runtime: dict[str, Any]
    started_at: str
    ended_at: str
    duration_seconds: float
    raw_outcomes: list[dict[str, Any]]
    aggregate_metrics: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def run_id(self) -> str:
        return canonical_hash(asdict(self))


def judged_dataset_fingerprint(dataset: JudgedDataset) -> str:
    rows = []
    for query in sorted(dataset.queries, key=lambda item: item.query_id):
        record = asdict(query)
        record.pop("adjudication_note", None)
        rows.append(record)
    return canonical_hash({"corpus_fingerprint": dataset.corpus_fingerprint, "queries": rows})


def create_queries_from_documents(
    documents: Iterable[dict[str, Any]], query_texts: list[str] | None = None, *, provenance: str = "human"
) -> list[JudgedQuery]:
    """Create reviewable query seeds from selected documents without inventing judgments."""
    queries: list[JudgedQuery] = []
    for index, document in enumerate(documents):
        document_id = str(document.get("id") or document.get("document_id") or "")
        if not document_id:
            continue
        metadata = document.get("metadata") or document
        query = (query_texts[index] if query_texts and index < len(query_texts) else document.get("query")) or f"What evidence is contained in {document_id}?"
        queries.append(JudgedQuery(
            query=str(query), query_class="selected_document", answerable=True,
            judgments=[EvidenceJudgment(document_id, str(document.get("source_span_id") or metadata.get("source_span_id") or document_id), 3)],
            expected_speakers=[str(metadata["speaker"])] if metadata.get("speaker") else [],
            expected_node_types=[str(metadata["node_type"])] if metadata.get("node_type") else [],
            date_start=str(metadata.get("episode_date") or ""), date_end=str(metadata.get("episode_date") or ""),
            acceptable_evidence_sets=[[document_id]], provenance=provenance,
            human_reviewed=provenance == "human", adjudication_state="pending",
        ))
    return queries


def grade_ranked_candidates(query: JudgedQuery, ranked_results: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
    grades = relevance_map(query)
    acceptable = [set(group) for group in query.acceptable_evidence_sets]
    graded = []
    for rank, item in enumerate(ranked_results, 1):
        record = {"id": str(item)} if isinstance(item, str) else dict(item)
        document_id = str(record.get("id") or record.get("document_id") or "")
        record.update({"rank": rank, "id": document_id, "grade": grades.get(document_id, 0), "hard_negative": document_id in query.hard_negative_ids})
        record["acceptable_set_hits"] = [document_id in group for group in acceptable]
        graded.append(record)
    return graded


class ExperimentStore:
    """Persist immutable run data independently from mutable operator notes."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, manifest: ExperimentManifest, report: dict[str, Any], notes: str = "") -> Path:
        run_dir = self.root / manifest.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        immutable = run_dir / "run.json"
        payload = {"manifest": asdict(manifest), "run_id": manifest.run_id, "report": report}
        encoded = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
        if immutable.exists() and immutable.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Immutable run {manifest.run_id} already exists with different data")
        immutable.write_text(encoded, encoding="utf-8")
        try:
            os.chmod(immutable, 0o444)
        except OSError:
            pass
        self.update_notes(manifest.run_id, notes)
        return run_dir

    def update_notes(self, run_id: str, notes: str) -> Path:
        path = self.root / run_id / "notes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"notes": notes}, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return path


@dataclass(frozen=True)
class ExperimentManifest:
    corpus_fingerprint: str
    collection_name: str
    index_identity: str
    retrieval_settings: dict[str, Any]
    model_settings: dict[str, Any]
    seeds: dict[str, int]
    timings: dict[str, float]
    code_version: str = "unknown"
    hardware: dict[str, str] = field(default_factory=lambda: {"platform": platform.platform(), "python": sys.version.split()[0]})
    contract_version: str = EXPERIMENT_VERSION
    judged_dataset_fingerprint: str = ""
    import_manifest_fingerprint: str = ""
    embedding_fingerprint: str = ""
    embedding_dimension: int | None = None
    representation_id: str = ""
    filter_settings: dict[str, Any] = field(default_factory=dict)
    context_settings: dict[str, Any] = field(default_factory=dict)
    projection_settings: dict[str, Any] = field(default_factory=dict)
    source_cache_ids: list[str] = field(default_factory=list)
    storage_bytes: int | None = None

    @property
    def run_id(self) -> str:
        return canonical_hash(asdict(self))

    @property
    def alignment_key(self) -> dict[str, str]:
        return {"corpus_fingerprint": self.corpus_fingerprint, "judged_dataset_fingerprint": self.judged_dataset_fingerprint, "contract_version": self.contract_version}


def relevance_map(query: JudgedQuery) -> dict[str, int]:
    return {item.document_id: item.grade for item in query.judgments}


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def _result_record(item: dict[str, Any] | str) -> dict[str, Any]:
    return {"id": str(item)} if isinstance(item, str) else dict(item)


def _result_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("document_id") or item.get("node_id") or "")


def _sources(results: list[dict[str, Any]]) -> list[str]:
    values = []
    for item in results:
        metadata = item.get("metadata") or {}
        values.append(str(item.get("source") or metadata.get("source") or metadata.get("source_file") or metadata.get("episode_id") or item.get("source_span_id") or _result_id(item)))
    return values


def retrieval_metrics(query: JudgedQuery, ranked_ids: list[dict[str, Any] | str], k: int = 10, recall_k: int = 20) -> dict[str, float]:
    results = [_result_record(item) for item in ranked_ids]
    grades = relevance_map(query)
    for item in results:
        item["id"] = _result_id(item)
        item["grade"] = grades.get(item["id"], 0)
    relevant = {doc_id for doc_id, grade in grades.items() if grade >= 2}
    top = results[:k]
    top_ids = [_result_id(item) for item in top]
    top_relevant = [doc_id for doc_id in top_ids if doc_id in relevant]
    ranked_grades = [grades.get(_result_id(item), 0) for item in top]
    ideal = sorted([grade for grade in grades.values() if grade >= 2], reverse=True)[:k]
    reciprocal = next((1 / (index + 1) for index, item in enumerate(results) if _result_id(item) in relevant), 0.0)
    recall_hits = len(set(_result_id(item) for item in results[:recall_k]).intersection(relevant))
    primary = {doc_id for doc_id, grade in grades.items() if grade == 3}
    acceptable_sets = [set(group) for group in query.acceptable_evidence_sets if group]
    sources = _sources(top)
    return {
        f"precision@{k}": len(top_relevant) / max(1, len(top)),
        f"recall@{recall_k}": recall_hits / max(1, len(relevant)),
        "mrr": reciprocal,
        f"ndcg@{k}": dcg(ranked_grades) / max(dcg(ideal), 1e-12) if ideal else 0.0,
        f"hit_rate@{k}": float(bool(top_relevant)),
        "no_answer_false_positive_rate": float(not query.answerable and any(grades.get(doc_id, 0) >= 2 for doc_id in top_ids)),
        "constraint_accuracy": constraint_accuracy(query, top),
        f"primary_coverage@{k}": len(set(top_ids).intersection(primary)) / max(1, len(primary)),
        f"duplicate_hit_rate@{k}": redundancy(top),
        f"source_diversity@{k}": len(set(sources)) / max(1, len(sources)),
        "acceptable_evidence_set_hit": float(any(set(top_ids).intersection(group) for group in acceptable_sets)) if acceptable_sets else 0.0,
        "hard_negative_hit_rate": float(any(_result_id(item) in query.hard_negative_ids for item in top)),
        "result_count": float(len(results)),
        f"false_primary_support@{k}": float(not query.answerable and any(grades.get(doc_id, 0) >= 2 for doc_id in top_ids)),
    }


def constraint_accuracy(query: JudgedQuery, results: list[dict[str, Any]]) -> float:
    if not results:
        return 1.0
    for result in results:
        metadata = result.get("metadata") or {}
        speaker = metadata.get("speaker")
        speakers = metadata.get("speakers") or ([speaker] if speaker else [])
        if query.expected_speakers and not set(query.expected_speakers).intersection(map(str, speakers)):
            return 0.0
        if query.expected_node_types and str(metadata.get("node_type") or metadata.get("level") or "") not in query.expected_node_types:
            return 0.0
        date = str(metadata.get("episode_date") or "")
        if query.date_start and (not date or date < query.date_start):
            return 0.0
        if query.date_end and (not date or date > query.date_end):
            return 0.0
    return 1.0


def redundancy(results: list[dict[str, Any]]) -> float:
    if len(results) < 2:
        return 0.0
    identities = _sources(results)
    return 1.0 - (len(set(identities)) / len(identities))


def aggregate_metric(rows: list[dict[str, float]], name: str) -> float:
    values = [row[name] for row in rows if name in row]
    return statistics.fmean(values) if values else 0.0


def evaluate_results(dataset: JudgedDataset, payload: dict[str, Any], *, k: int = 10, recall_k: int = 20) -> dict[str, Any]:
    """Evaluate an imported ranked-result artifact and retain every per-query ranking."""
    by_query = {str(item.get("query_id")): item for item in payload.get("results", [])}
    rows: list[dict[str, Any]] = []
    for query in dataset.queries:
        source = by_query.get(query.query_id, {})
        ranked = source.get("ranked_results") or source.get("ranked_ids") or []
        graded = grade_ranked_candidates(query, ranked)
        metrics = retrieval_metrics(query, graded, k=k, recall_k=recall_k)
        metrics["latency_ms"] = float(source.get("latency_ms") or source.get("latency") or 0.0)
        rows.append({
            "query_id": query.query_id,
            "query": query.query,
            "answerable": query.answerable,
            "provenance": query.provenance,
            "ranked_results": graded,
            "ranked_ids": [_result_id(item) for item in graded],
            **metrics,
        })
    names = list(METRIC_KEYS) + ["acceptable_evidence_set_hit", "hard_negative_hit_rate"]
    aggregate = {name: aggregate_metric(rows, name) for name in names}
    aggregate["median_latency_ms"] = statistics.median([float(row.get("latency_ms", 0)) for row in rows]) if rows else 0.0
    aggregate["storage_bytes"] = int(payload.get("storage_bytes") or 0)
    return {
        "contract_version": REPORT_VERSION,
        "dataset_id": dataset.dataset_id,
        "corpus_fingerprint": dataset.corpus_fingerprint,
        "judged_dataset_fingerprint": dataset.fingerprint,
        "query_count": len(rows),
        "results_fingerprint": canonical_hash([{"query_id": row["query_id"], "ranked_ids": row["ranked_ids"]} for row in rows]),
        "queries": rows,
        "aggregate": aggregate,
        "source": payload.get("source") or "imported_results",
    }


def evaluate(dataset_path: Path, results_path: Path) -> dict[str, Any]:
    return evaluate_results(JudgedDataset.load(dataset_path), json.loads(results_path.read_text(encoding="utf-8")))


def paired_bootstrap(baseline: list[float], candidate: list[float], samples: int = 10_000, confidence: float = 0.95, seed: int = 42) -> dict[str, Any]:
    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("Paired bootstrap requires non-empty equal-length samples")
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        indices = [rng.randrange(len(baseline)) for _ in baseline]
        deltas.append(statistics.fmean(candidate[index] - baseline[index] for index in indices))
    deltas.sort()
    alpha = (1.0 - confidence) / 2.0
    low = deltas[int(alpha * (len(deltas) - 1))]
    high = deltas[int((1.0 - alpha) * (len(deltas) - 1))]
    return {"mean_delta": statistics.fmean(c - b for b, c in zip(baseline, candidate)), "confidence": confidence, "low": low, "high": high, "samples": samples, "paired_queries": len(baseline), "descriptive_only": len(baseline) < 30, "seed": seed}


def promotion_decision(baseline: dict[str, float], candidate: dict[str, float]) -> dict[str, Any]:
    failures = []
    if candidate.get("ndcg@10", 0) < baseline.get("ndcg@10", 0):
        failures.append("nDCG@10 regressed")
    if candidate.get("recall@20", 0) < baseline.get("recall@20", 0):
        failures.append("Recall@20 regressed")
    if candidate.get("constraint_accuracy", 0) < 1.0:
        failures.append("Hard-filter correctness is below 100%")
    base_latency = baseline.get("median_latency_ms", 0)
    if base_latency and candidate.get("median_latency_ms", 0) > base_latency * 1.25:
        failures.append("Median latency regressed by more than 25%")
    if candidate.get("no_answer_false_positive_rate", candidate.get("false_primary_support", 0)) > baseline.get("no_answer_false_positive_rate", baseline.get("false_primary_support", 0)):
        failures.append("No-answer false-positive rate regressed")
    if candidate.get("duplicate_hit_rate@10", 0) > baseline.get("duplicate_hit_rate@10", 0):
        failures.append("Duplicate-hit rate regressed")
    return {"promote": not failures, "failures": failures, "warnings": []}


def pareto_frontier(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier = []
    for point in points:
        quality = float(point.get("quality") or 0.0)
        latency = float(point.get("latency_ms") or math.inf)
        storage = float(point.get("storage_bytes") or math.inf)
        dominated = any(
            float(other.get("quality") or 0.0) >= quality
            and float(other.get("latency_ms") or math.inf) <= latency
            and float(other.get("storage_bytes") or math.inf) <= storage
            and other is not point
            for other in points
        )
        if not dominated:
            frontier.append(point)
    return frontier


def _alignment(report: dict[str, Any]) -> tuple[str, str]:
    return str(report.get("corpus_fingerprint") or ""), str(report.get("judged_dataset_fingerprint") or "")


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any], *, samples: int = 10_000, seed: int = 42) -> dict[str, Any]:
    if _alignment(baseline) != _alignment(candidate) or not all(_alignment(baseline)):
        raise IncompatibleComparisonError("Runs must share non-empty corpus_fingerprint and judged_dataset_fingerprint")
    base_rows = {str(row.get("query_id")): row for row in baseline.get("queries") or []}
    candidate_rows = {str(row.get("query_id")): row for row in candidate.get("queries") or []}
    if set(base_rows) != set(candidate_rows):
        raise IncompatibleComparisonError("Runs do not contain the same judged query IDs")
    paired = []
    for query_id in sorted(base_rows):
        left, right = base_rows[query_id], candidate_rows[query_id]
        deltas = {}
        for metric in METRIC_KEYS:
            if metric in left or metric in right:
                deltas[metric] = {"baseline": left.get(metric, 0), "candidate": right.get(metric, 0), "delta": float(right.get(metric, 0)) - float(left.get(metric, 0))}
        quality_delta = deltas.get("ndcg@10", {"delta": 0})["delta"]
        outcome = "tie" if quality_delta == 0 else ("win" if quality_delta > 0 else "loss")
        paired.append({"query_id": query_id, "query": left.get("query", right.get("query", "")), "outcome": outcome, "deltas": deltas})
    intervals = {}
    for metric in METRIC_KEYS:
        left_values = [float(base_rows[q].get(metric, 0)) for q in sorted(base_rows)]
        right_values = [float(candidate_rows[q].get(metric, 0)) for q in sorted(base_rows)]
        intervals[metric] = paired_bootstrap(left_values, right_values, samples=samples, seed=seed)
    base_aggregate = baseline.get("aggregate", {})
    candidate_aggregate = candidate.get("aggregate", {})
    points = [
        {"run": "baseline", "quality": base_aggregate.get("ndcg@10", 0), "latency_ms": base_aggregate.get("latency_ms", base_aggregate.get("median_latency_ms", 0)), "storage_bytes": base_aggregate.get("storage_bytes", 0)},
        {"run": "candidate", "quality": candidate_aggregate.get("ndcg@10", 0), "latency_ms": candidate_aggregate.get("latency_ms", candidate_aggregate.get("median_latency_ms", 0)), "storage_bytes": candidate_aggregate.get("storage_bytes", 0)},
    ]
    return {
        "contract_version": REPORT_VERSION,
        "alignment": {"corpus_fingerprint": baseline["corpus_fingerprint"], "judged_dataset_fingerprint": baseline["judged_dataset_fingerprint"]},
        "paired_queries": len(paired),
        "wins": sum(item["outcome"] == "win" for item in paired),
        "losses": sum(item["outcome"] == "loss" for item in paired),
        "ties": sum(item["outcome"] == "tie" for item in paired),
        "per_query": paired,
        "worst_regressions": sorted([item for item in paired if item["outcome"] == "loss"], key=lambda item: item["deltas"].get("ndcg@10", {}).get("delta", 0))[:10],
        "bootstrap": intervals,
        "pareto": {"points": points, "frontier": pareto_frontier(points)},
        "promotion": promotion_decision(base_aggregate, candidate_aggregate),
    }


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    promotion = comparison.get("promotion", {})
    lines = ["# RAGScope Evaluation Comparison", "", f"Promotion: **{'PASS' if promotion.get('promote') else 'FAIL'}**", f"Paired queries: {comparison.get('paired_queries', 0)}", "", "## Per-query outcomes", "", "| Query | Outcome | nDCG delta | Recall delta | Latency delta |", "|---|---:|---:|---:|---:|"]
    for row in comparison.get("per_query", []):
        deltas = row.get("deltas", {})
        lines.append(f"| {row.get('query_id')} | {row.get('outcome')} | {deltas.get('ndcg@10', {}).get('delta', 0):.4f} | {deltas.get('recall@20', {}).get('delta', 0):.4f} | {deltas.get('latency_ms', {}).get('delta', 0):.2f} |")
    lines.extend(["", "## Guardrails", ""])
    failures = promotion.get("failures") or ["No promotion guardrail failures."]
    lines.extend(f"- {'FAIL' if promotion.get('failures') else 'PASS'}: {failure}" for failure in failures)
    lines.extend(["", "## Worst regressions", ""])
    lines.extend(f"- {row.get('query_id')}: {row.get('deltas', {}).get('ndcg@10', {}).get('delta', 0):.4f}" for row in comparison.get("worst_regressions", []))
    return "\n".join(lines) + "\n"
