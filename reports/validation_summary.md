# Validation summary — 2026-09-24

## Executed checks

- Python 3.11.12 in `.venv311`; regular wheel installation succeeds and installed Python sources match the repository byte-for-byte.
- `python -m pytest -q`: **89 passed**, 3 FAISS/SWIG deprecation warnings.
- `ruff check src scripts tests`: passed.
- `ruff format --check src scripts tests`: passed (26 files).
- `python -m pip check`: no broken requirements.
- Rebuilt all four local PDFs: **1,155 evidence items**, **565 indexed chunks**. The extractor explicitly rejected 44 sparse/grid table candidates and recorded these warnings. Zero accepted tables for P01/P03 is a known extraction limitation, not a claim that those PDFs lack tables.
- Actual CLI ask, compare (two cited sources), inspect and parseable JSON output: passed.
- Baseline run: `results/final-20260924`, **36 predictions** over 12 draft questions and 3 modes.
- Evaluation run twice against the same predictions: both succeeded and produced the report.
- Ablations: `results/final-ablations-20260924`, **132 predictions** covering k=3/5/10 and no-caption variants; each directory evaluated successfully.
- Data audit: no missing paper/page references; **237 extraction items** sampled for human review. Review is pending.

## Interpretation

These are offline lexical/extractive runs. They demonstrate pipeline execution, deterministic retrieval and structural citation validation. They do not establish LLM accuracy, semantic support, VLM capability, or human-verified gold quality. Structural precision in the delivered text/table run is 14/14 citations; coarse page-level evidence recall is 11/18 for each. These small, development-set measurements must not be generalized.

See `experiment_report.md` for the generated report, `failure_analysis.md` for five observed failure diagnoses and `requirements_status.md` for the complete remaining research scope.

## Environment issue resolved

The original Python 3.9 environment segfaulted while importing readline. A separate Python 3.11 environment resolves that failure. On this macOS host, editable `.pth` files were subsequently marked hidden and skipped by Python; a regular wheel installation avoids the issue. Reinstall the package after source edits using `python -m pip install --no-deps .`.

No live API inference, API charges, remote model downloads, or hosted CI runs were performed. Old generated snapshots were retained separately; the current defaults use `artifacts/current`.
