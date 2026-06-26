# Roadmap

This roadmap defines how `RAGScope` should become the evaluation and comparison surface for both baseline and high-context podcast RAG workflows.

## Compatibility Principles

- Keep existing inspection and browsing workflows working with current exports.
- Treat high-context evaluation as additive, not required.
- Accept both older baseline artifacts and newer richer manifests.
- Make cross-profile comparisons a first-class feature instead of assuming one canonical pipeline mode.

## Shared Runtime Profile Model

- Add support for reading and displaying:
  - `runtime_profile`
  - `backend`
  - `model_name`
  - `model_capabilities`
  - `structured_output_used`
  - `judge_pass_used`
- Distinguish:
  - baseline preprocessing
  - high-context preprocessing
  - baseline chat synthesis
  - high-context chat synthesis

## Core Product Direction

- Make `RAGScope` the main evaluation harness for the podcast stack.
- Focus on comparisons that answer:
  - did longer context improve attribution?
  - did structured extraction reduce malformed outputs?
  - did a judge pass reduce contradictions?
  - where does the baseline path remain sufficient?

## Evaluation Features

- Add profile-aware dashboards comparing:
  - fallback rate
  - malformed JSON rate
  - duplicate summary rate
  - contradiction rate
  - speaker-attribution quality
  - belief-over-time answer quality
- Add side-by-side views:
  - baseline vs high-context processed cache
  - baseline vs high-context answer synthesis
  - workhorse model vs judge model

## Data And Metadata

- Read additive metadata from processed caches, import manifests, and `podcast.json`.
- Keep older artifacts readable by treating missing advanced fields as unknown rather than invalid.
- Store evaluation runs with:
  - source artifact identifiers
  - runtime profiles
  - model names
  - backend type
  - scoring results

## UX

- Add filters for:
  - runtime profile
  - backend
  - model
  - export compatibility status
- Add saved views for common comparisons:
  - `baseline_vs_5090`
  - `timeline_quality`
  - `speaker_attribution_failures`
  - `fallback_hotspots`

## Testing

- Add fixtures for:
  - baseline exports
  - high-context exports
  - mixed-profile datasets
- Add regression tests for:
  - metadata parsing
  - comparison scoring
  - missing-field tolerance
  - saved comparison views

## Implementation Phases

1. Add metadata readers for runtime profile, backend, and advanced provenance fields.
2. Add cross-profile comparison views for processed caches and exports.
3. Add evaluation metrics for attribution, fallback rate, malformed output rate, and contradiction rate.
4. Add saved comparison presets and profile-aware filters.
5. Add regression fixtures proving that both old and new artifacts remain readable.
