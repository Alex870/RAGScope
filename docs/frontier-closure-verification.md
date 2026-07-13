# Frontier Closure Verification

Verified: 2026-07-13

- Dependency-backed Python tests construct and close a temporary Chroma collection from committed JSON vectors.
- Projection, clustering, immutable-run, metrics, promotion, and counterfactual-lineage tests run with scientific dependencies installed.
- The production React/Vite frontend builds with Node 22-compatible dependencies.
- The deterministic synthetic benchmark passes its committed promotion baseline.
- GitHub Actions targets Windows and Ubuntu with Python 3.12 and Node 22.
- Local GPU verification used an NVIDIA GeForce RTX 5070 Ti with CUDA-enabled PyTorch `2.7.1+cu128`; hosted CI is expected to remain CPU-only.
