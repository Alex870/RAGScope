# Roadmap

This roadmap captures practical feature upgrades for `RAGScope`, the React/FastAPI workbench for inspecting vector stores, retrieval behavior, metadata health, and RAG quality.

## Highest-Impact Improvements

- Add side-by-side database comparison. Load two Chroma exports and compare metadata completeness, embedding neighborhoods, speaker/date coverage, duplicate rates, retrieval results, and audit scores.
- Add temporal viewpoint analysis for podcast RAG collections. For a selected speaker and topic, show matching chunks and position cards across time so belief evolution can be inspected visually.
- Add a query workbench that stores benchmark queries, expected metadata filters, retrieved results, notes, and pass/fail judgments as reusable evaluation sets.
- Add contract validation for podcast exports. Detect missing `speaker`, `episode_date`, `episode_sort_key`, `node_type`, `node_id`, parent/child links, and embedding-model metadata before deeper analysis.
- Add exportable audit reports as Markdown/HTML/JSON so findings can be archived, shared, or attached to project notes.

## Visualization And Exploration

- Add linked views between the 2D/3D map, table, metadata inspector, hierarchy graph, and retrieval results.
- Add a hierarchy view for RAPTOR-style documents showing leaf chunks, cluster summaries, episode thesis documents, and position cards.
- Add timeline and heatmap views for podcast collections: documents per episode, speaker coverage, node-type counts, position-card density, and retrieval hit distribution.
- Add nearest-neighbor graph visualization with controls for edge count, distance threshold, node type, speaker, and date range.
- Add cluster drill-down pages with representative chunks, topic keywords, centroid documents, outliers, and cross-cluster similarity.

## Retrieval Evaluation

- Add multi-strategy retrieval experiments: vector-only, metadata-filtered, position-card-first, hybrid keyword/vector, MMR/diversity, and reranked retrieval.
- Add recall and diversity diagnostics for a saved query set, including duplicate-hit rate, episode spread, speaker spread, date coverage, and node-type balance.
- Add context-window simulation that shows what would be sent to a chat model under different context budgets.
- Add answer-grounding checks when an LLM interpretation is enabled, separating deterministic retrieval quality from generated-answer quality.
- Add regression comparison between saved audit runs so preprocessing/import changes can be measured instead of judged by feel.

## Data Quality Diagnostics

- Add duplicate and near-duplicate content reports with suggested causes, such as overlapping chunk windows or repeated sponsor blocks.
- Add metadata anomaly detection for impossible dates, missing timestamps, inconsistent speaker lists, orphaned parent/child IDs, and mismatched source paths.
- Add embedding anomaly views for outlier chunks, collapsed clusters, unusually dense duplicate neighborhoods, and missing embeddings.
- Add speaker/entity coverage reports to reveal which speakers or episodes are underrepresented after filtering/import.
- Add processed-cache-to-Chroma traceability if import manifests are available.

## User Experience

- Break the large frontend `App.jsx` into focused components for loading, map controls, audit workspace, saved views, table, inspector, and settings. This will make feature work much easier.
- Add a first-run onboarding flow that explains how to point RAGScope at a Chroma export and what the major views mean.
- Add saved comparison sessions, saved query sets, and named audit runs in addition to saved views.
- Add keyboard shortcuts for search, selected-point focus, table navigation, save view, and clear filters.
- Add clearer progress and cancellation UI for expensive projection, clustering, audit, and LLM-assisted operations.

## Backend And Performance

- Add cache invalidation keyed by Chroma path, collection name, collection modification time, reducer settings, and clustering settings.
- Add streaming/progress endpoints for long-running reductions, clustering, and audit jobs.
- Add server-side pagination and filtering for very large collections so the browser is not asked to hold more rows than needed.
- Add optional approximate-nearest-neighbor analysis for large collections where pairwise comparisons become expensive.
- Add benchmark telemetry for load time, projection time, clustering time, audit time, memory use, and response sizes.

## Testing And Packaging

- Add backend tests for Chroma loading, metadata filters, reducers, clustering fallback, topic labeling, saved views, and audit scoring.
- Add frontend smoke tests for loading a sample dataset, selecting points, filtering metadata, running search, saving/loading views, and rendering audit results.
- Add a small synthetic Chroma fixture or serialized dataset so tests do not require a large local database.
- Add a production build smoke test and document a portable Windows packaging path.
- Add a diagnostic bundle command that captures runtime config, backend logs, package versions, Chroma metadata summary, and recent audit results.
