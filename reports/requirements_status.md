# Requirements status — 2026-09-24

This is a working, tested engineering MVP. It is **not a completed research study**, and the original brief's entire definition of done has not been met. No human annotation or real-model results have been fabricated.

| Requirement | Status and evidence |
|---|---|
| Python 3.11+, locked dependencies, CLI, typed contracts | Implemented. Dedicated `.venv311`, `requirements.lock`, Pydantic schemas, JSON logging. |
| Offline deterministic path | Implemented. Lexical-hash retrieval + literal evidence quotation baseline. Mock embeddings remain explicitly test-only. |
| PDF extraction, provenance, failures and bounds | Implemented. Text/caption/table/embedded image extraction; pages, IDs, sections and available bounding boxes; PDF size/page bounds, source hashes, safe paper IDs, persisted extraction errors. OCR and complete rendered/vector-figure extraction are not implemented. |
| Chunking, dedup, immutable snapshots | Implemented. IDs local to each source evidence, cross-page/paper provenance retained, fixed normalized FAISS index, saved manifest/config/checksums. Existing corpus/index/run paths cannot be overwritten. |
| Retrieval | Implemented. Full small-index filtering before top-k, scores and modalities, config/model mismatch rejection. No reranker. |
| Cited answer and abstention | Implemented structural guard: exact ID/paper/page, citation coverage, no/low evidence abstention, raw response and prompt preserved. This does not prove semantic entailment or adequate evidence. |
| Compare and inspect | Implemented. Per-paper evidence table, unsupported comparisons flagged, extraction health and source excerpts shown. |
| Prompt injection protection | Documents serialized as data, no execution tools, deterministic injection regressions and fail-closed citation output tests. Arbitrary remote-model injection resistance is not established. |
| Reproducible benchmark | Implemented shared CLI/script pipeline, immutable question snapshot and hashes, k/settings/model/hardware/version metadata, raw predictions/evidence/prompts, per-mode saved outputs. |
| Baseline and ablation runs | Executed with the offline generator: three baselines, k=3/5/10, and no-caption variants. Results are software/lexical-baseline measurements, not LLM quality claims. |
| Metrics | Implemented structural precision from raw citations, citation coverage, exact-ID/page-fallback recall, abstention precision/recall, p50/p95, usage, per-category/modality/split, numerator/denominator and null undefined values. Correctness/semantic support require supplied judgments. API dollar cost remains unmeasured. |
| Blinded scoring | Implemented review templates, separate ID key, import script and evaluator judgment support. No human scores supplied. |
| Failure analysis | Five observed cases with source references and retrieved excerpts in `failure_analysis.md`; AI-authored diagnosis, not human rubric scoring. |
| Corpus licenses | Corrected metadata after checking source pages. P01–P03 use arXiv's non-exclusive distribution license, P04 CC BY 4.0. The current corpus does not meet the permissive-license-only scope. |
| Dataset size | Still four papers and 12 legacy questions. Needs a separate 10–20-paper, 30–50-question research dataset. |
| Human-authored/verified gold | Not established. Drafts and AI corrections are explicitly unverified. Independent authorship/annotation must not be claimed. |
| Held-out set | No untouched held-out set exists. Split support is implemented; existing questions were used during development and must not be relabeled as unseen. |
| 20% extraction review | Deterministic stratified review sample generated. Human review remains pending. |
| Real generator/VLM | Optional adapters retained, real API/model inference untested. `vlm-rag` is rejected rather than masquerading as caption-only reasoning. |
| README/results/CI | Updated runnable setup and commands, limitations, protocol, measured report and offline CI workflow. CI configuration exists; local checks were run, hosted CI was not. |

The software can support completing the study. The remaining research work requires new appropriately licensed sources, independently authored/verified annotations, actual model inference, and completed human review. Generating extra draft questions or calling AI labels “human verified” would not satisfy those requirements.
