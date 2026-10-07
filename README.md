# ResearchPilot

[![CI](https://github.com/ngbao12/researchPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ngbao12/researchPilot/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A local workspace for reading scientific papers, asking questions, and comparing findings with page-level source evidence.

ResearchPilot combines a bilingual English/Vietnamese web interface with a reproducible command-line retrieval pipeline. Use offline quotations without an API key, or connect Groq, Gemini, or OpenAI to synthesize answers from selected papers.

**Status:** experimental, single-user software for localhost. Citation checks establish that quoted evidence exists in a source; they do not independently verify every interpretation made by a model. The project has no independent evaluation supporting a general accuracy claim.

## Features

- Import local PDFs, public PDF URLs, and arXiv links; detect duplicates and persist the library.
- Ask questions about selected papers or compare exactly two papers.
- Inspect evidence beside each answer and open the original PDF page.
- Expand long excerpts and distinguish cited evidence from unused retrieval candidates.
- Switch between English and Vietnamese; export session answers as Markdown.
- Configure API providers and models in the browser, or use a server-side Groq key pool.
- Run CLI benchmarks, ablations, citation checks, and human-review exports.

## Quick start

Use **Python 3.11 or newer**. Local validation uses Python 3.11. Run commands from the repository root; configuration and data paths are relative to it.

### 1. Install

```bash
git clone https://github.com/ngbao12/researchPilot.git
cd researchPilot
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[api]'
```

On Windows, create the environment with `py -3.11 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1` in PowerShell. Windows support has not been locally validated.

For offline use, install `-e .` instead of `-e '.[api]'`. For the pinned offline development dependencies, install `-r requirements.lock`, then `-e . --no-deps`. The lock file does not include the optional API or semantic-embedding dependencies and is not a hash-verified lock.

### 2. Build the initial library

```bash
python scripts/build_corpus.py --config configs/default.yaml
```

This downloads the papers in [the manifest](data/papers_manifest.json), extracts their contents, and builds `artifacts/current`. Internet access is required unless the PDFs already exist. Use `--skip-download` when all manifest PDFs are available locally.

**Complete this step before starting the web app for the first time.** You do not need to rebuild on every launch. Add further papers through the interface.

PDF fingerprints are checked against the manifest. If an upstream paper has changed, obtain the matching version or create a separately reviewed manifest; do not bypass a mismatch by silently replacing its hash. PDFs and generated indexes are local data, not part of a fresh source checkout.

### 3. Start the app

```bash
researchpilot-web --root . --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Stop the foreground server with `Ctrl+C`.

Alternatively, `python scripts/start_web.py` starts a background server and reuses an existing healthy server on that port. Its log and PID are written to `tmp/web-server.log` and `tmp/web-server.pid`. Use `--port 8766` to select another port.

## Using the workspace

1. Select papers in the library or use the import button.
2. Open the model connection settings. Select **Offline**, or enter a provider, API key, and model ID available to your account. Test the connection and apply the settings.
3. Ask a question, or choose the comparison mode with exactly two papers selected.
4. Read the answer alongside its evidence. Click a citation to inspect the PDF page.
5. Export useful answers as Markdown before closing or reloading the tab.

Example questions:

- “How does MobileNet reduce computational cost?”
- “What ImageNet accuracy does EfficientNet-B7 report?”
- “How do these two papers approach model scaling?”

The language switch controls the interface and subsequent answers. It does not translate existing answers or verbatim source passages. Long excerpts can be expanded; the additional context view retains extracted source text.

### PDF imports

Web imports accept PDFs up to **30 MB and 200 pages**. Scanned documents need external OCR first. SHA-256 fingerprints identify duplicates. Imports are stored under `data/papers` and `artifacts/library_versions`, with `artifacts/library-active.json` selecting the active library. Failed imports do not replace the active library. URLs resolving to private networks are rejected.

## API configuration and privacy

| Mode | Configuration |
| --- | --- |
| Offline quotations | Select Offline; no API key required |
| Personal Groq, Gemini, or OpenAI connection | Enter a key and model ID in the web settings |
| Default Groq connection | Set `GROQ_API_KEY` in the environment or `.env.local` |
| Groq fallback keys | Set comma-separated `GROQ_API_KEYS` |

To configure server-side defaults:

```bash
cp .env.example .env.local
# Edit .env.local with your own values.
chmod 600 .env.local
```

Restart the server after changing these defaults. Nonempty environment values take precedence over `.env.local`. No shared API key is provided by this repository.

- Custom keys stay in tab memory and are sent to the local server with requests. Reloading or closing the tab clears custom keys and session history; the language preference is stored separately in browser storage.
- Server-side default keys are not returned to the browser. Custom keys do not use the server's fallback key pool.
- A blank custom key falls back to the configured server-side Groq connection, if one exists.
- Questions and selected evidence are sent to the chosen provider. Planning, evidence selection, and citation repair may involve additional calls, latency, and token charges.
- Multiple Groq keys can share a quota. Adding keys does not guarantee additional capacity.
- The connection test checks model access, not successful answer generation or remaining quota.

Gemini uses the OpenAI-compatible adapter. Provider routing and error handling are covered by mocked tests; live provider behavior still depends on account permissions and service availability.

## How it works

```text
PDFs → page extraction → retrieval candidates → evidence selection
                                                      ↓
                              model claims + source identifiers
                                                      ↓
                              source validation → cited answer
```

The API-backed web `table-rag` path retrieves page text, preserves table context, and can reformulate Vietnamese questions for retrieval. Broad questions add opening and closing pages and an LLM-based evidence selection step. This still depends on the candidate set; it is not embedding search over every page.

Models select existing evidence identifiers. The server validates sources and attaches paper/page references, with one repair attempt for some citation formatting failures. It can withhold unsupported answers or return a supported partial answer with missing information identified. Model-written explanations are not independent verification, and retrieval scores are not probabilities of correctness.

Other modes and CLI benchmarks use the original extraction → provenance-aware chunks → FAISS index → retrieval → generation → citation-validation pipeline. CLI results do not fully measure the newer web workflow.

## Command-line usage

The [default configuration](configs/default.yaml) uses lexical retrieval and literal offline quotations.

```bash
researchpilot ask --question "What is the key architectural innovation in MobileNets?" --paper-id P01
researchpilot ask --question "What accuracy does EfficientNet-B7 achieve?" --paper-id P02 --mode table-rag --json
researchpilot compare --paper-a P01 --paper-b P02 --question "How do width and resolution scaling differ?"
researchpilot inspect --query "depthwise separable convolution" --paper-id P01
```

For OpenAI-backed CLI generation, set `OPENAI_API_KEY` in the environment or `.env`, copy the default configuration, and set `generate.llm_provider: openai` and `generate.llm_model`. Run `researchpilot --config PATH ...`. CLI configuration is separate from web connection settings.

Optional sentence-transformer embeddings require `python -m pip install -e '.[semantic]'`. Rebuild the index after changing the embedding provider, model, or dimension.

### Evaluation

```bash
researchpilot benchmark --questions data/questions.jsonl --out results/my-run
researchpilot evaluate --run results/my-run --out reports/my-run.md
python scripts/run_baselines.py --questions data/questions.jsonl --out results/ablation-run --ablations
python scripts/audit_data.py --out reports/data-audit
```

Use a fresh output directory for each benchmark; existing predictions are not overwritten. When passing a different `--index-dir`, keep the embedding configuration consistent with that index.

Structural citation validity, coverage, and evidence recall measure different things. Answer correctness and semantic support require human review. The legacy questions were used during development and are not an untouched held-out set.

## Development

```bash
python -m pip install -e '.[dev,api]'
ruff check src scripts tests
pytest -q
node --check src/researchpilot/web_assets/app.js
node --check src/researchpilot/web_assets/i18n.js
python -m pip wheel --no-deps . --wheel-dir dist
```

Tests use synthetic PDFs and mocked providers; they do not require a downloaded corpus or API keys. Node.js is needed only for JavaScript syntax checks. GitHub Actions runs lint, tests, asset checks, and a package build on Python 3.11 and 3.12.

```text
configs/                  Pipeline configuration
src/researchpilot/        Extraction, retrieval, generation, CLI, and web server
src/researchpilot/web_assets/  Browser interface
scripts/                  Corpus, evaluation, audit, and startup helpers
tests/                    Automated regression tests
data/                     Source manifest and draft evaluation questions
reports/                  Historical evaluation and validation notes
artifacts/                Local generated corpus and indexes (ignored)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| Missing corpus or index | Build the initial library from the repository root |
| Package import fails | Activate the virtual environment and run `python -m pip install -e .` |
| Browser cannot connect | Start the server; inspect `tmp/web-server.log` if using the background helper |
| Invalid key or inaccessible model | Check provider, key, and model ID in connection settings |
| HTTP 429 | Check account quota and rate limits; wait or choose another provider |
| Empty model response | Retry or select a different model; the connection test does not generate content |
| Insufficient evidence | Confirm the selected papers, inspect sources, and narrow the question |
| Interface appears stale | Export useful notes, reload the page, and ask again |

## Limitations and research status

- The server binds to `127.0.0.1` and has no multi-user authentication. Public deployment is outside its current design.
- PDF extraction can mix columns, split words, or misread tables. Integrated OCR and full visual reasoning are not implemented.
- `caption-rag` uses text/captions; it is not a vision-model analysis of figures. The `vlm-rag` evaluation path is incomplete.
- Offline mode quotes sources; it does not synthesize or compare findings like an LLM.
- Model evidence selection and explanations can be wrong. The current dataset is insufficient for broad research claims.

Further context: [data provenance](data/README.md), [requirements status](reports/requirements_status.md), [experiment report](reports/experiment_report.md), [failure analysis](reports/failure_analysis.md), and [web validation notes](reports/ui-import-gemini-evidence-20260924.md). Historical reports describe the versions and runs recorded at their dates.

## License

Project source code is licensed under the [MIT License](LICENSE). Papers and other third-party material retain their own licenses; see [data provenance](data/README.md). Local PDFs, indexes, caches, and new benchmark runs are ignored. Historical evaluation results remain tracked for the accompanying reports; older Git history may still contain PDFs and generated artifacts.
