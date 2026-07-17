# Local Podcast Evaluation Pack v1

`podcast-evaluation-pack-v1` references local/private data; it does not copy audio or transcripts. Create an empty template with:

```powershell
python -m server.evaluation_pack_cli template benchmarks/local/my-pack.json --pack-id my-pack
```

Populate `episodes` with stable episode IDs, paths, SHA-256 hashes, optional transcript references, selected audio ranges, duration, speaker labels and aliases, glossary/protected terms, condition tags, and notes. Populate the nested judged dataset with human-reviewed queries, acceptable evidence sets, answerability, constraints, reference claims, reviewer provenance, and adjudication state.

Validate without modifying source data:

```powershell
python -m server.evaluation_pack_cli validate benchmarks/local/my-pack.json
```

Optional JSON arrays of current document IDs and source-span IDs can be supplied with `--document-ids` and `--source-span-ids`. Validation reports missing paths, changed hashes, stale evidence IDs, incomplete judgments, and separate transcription/retrieval/answer readiness. The API equivalent is `POST /api/evaluation/packs/validate`.

Real episodes, excerpts, transcript references, judgments, and reviewer identities remain local and require human approval. Synthetic fixtures may be committed; private media and credentials must not be committed.
