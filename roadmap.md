# Roadmap

`RAGScope` is the measurement and investigation workbench for the podcast RAG stack. Its primary job is to make retrieval, contracts, and changes between builds observable and comparable. Embedding maps are useful exploratory tools, not proof of retrieval quality.

## Principles

- Keep local exploration fast for existing Chroma exports.
- Make audits and comparisons reproducible from saved inputs, settings, and artifact IDs.
- Separate deterministic retrieval measurements from LLM interpretation.
- Treat UMAP, clusters, and topic labels as diagnostic views, not ground truth.
- Report missing advanced metadata as reduced evaluability, not an assumed failure.

## Current Foundation

- React/FastAPI workbench with 2D/3D maps, clustering, metadata filters, search, saved views, retrieval experiments, and quality audits.
- Optional LLM-assisted audit/query generation with persisted state and backend service modules.

## Priority 1: Evaluation Dataset And Retrieval Metrics

- Add versioned query sets with relevance judgments and expected speaker/date/node-type constraints.
- Report Recall@k, MRR, nDCG, evidence coverage, duplicate-hit rate, diversity, latency, and result-set size.
- Support graded relevance and per-query failure diagnosis.
- Save each run with collection and embedding fingerprints, query-set version, filters, IDs, and scores.
- Export reusable evaluation sets and Markdown/HTML/JSON reports.

## Priority 2: Contract And Provenance Inspection

- Validate exports against the shared importer/chat contract.
- Surface embedding fingerprint/dimension, collection version, source IDs, hierarchy coverage, and speaker/date completeness.
- Trace vector records through export metadata to processed-cache nodes when provenance is available.
- Separate hard violations from incomplete-but-readable data.

## Priority 3: Comparative Experiments

- Compare exports only with an aligned corpus and judged query-set protocol.
- Add named experiments for chunking, embedding migration, import mode, hierarchy depth, reranking, and context budget.
- Show per-query metric deltas and regression thresholds.
- Store model/runtime metadata as provenance, not the comparison category itself.

## Priority 4: Analysis And UX

- Add linked hierarchy, retrieval, cluster, and temporal views with clear scope labels.
- Explain ranking signals, active filters, neighbors, and source provenance per result.
- Add background progress, cancellation, and server-side pagination for large collections.
- Persist seeds and reducer/clustering settings for reproducible visuals.

## Priority 5: LLM-Assisted Audit Discipline

- Run LLM interpretation only after deterministic audit data completes.
- Show model/context/prompt/completion/raw-response/parse diagnostics on every assisted result.
- Make evidence-limiting controls explicit.
- Calibrate LLM judgments against human review before using them in scores.
- Support LM Studio native v1 capability discovery with OpenAI-compatible fallback.

## Priority 6: Tests And Packaging

- Add synthetic Chroma, contract, and evaluation-set fixtures.
- Test metrics, comparison, provenance parsing, cache invalidation, missing-field tolerance, and frontend workflows.
- Add a portable Windows distribution and diagnostic bundle after clean-machine tests pass.

## Sequencing

1. Define shared contract and judged query set.
2. Make retrieval-run recording and metrics reliable.
3. Add comparison with regression thresholds.
4. Add provenance and linked diagnostics.
5. Scale large-collection execution and package the mature tool.
