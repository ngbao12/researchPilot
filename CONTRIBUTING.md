# Contributing to ResearchPilot

For bug fixes, include a concise reproduction and a regression test when behavior changes. Discuss larger changes in an issue before starting implementation.

## Local setup

Use Python 3.11+, create and activate a virtual environment, then run:

```bash
python -m pip install -e '.[dev,api]'
ruff check src scripts tests
pytest -q
node --check src/researchpilot/web_assets/app.js
node --check src/researchpilot/web_assets/i18n.js
python -m pip wheel --no-deps . --wheel-dir dist
```

Node.js is only required for the browser script checks. Automated tests use synthetic PDFs and mocked providers; no API keys or downloaded corpus are needed. Follow the README to build a real library and manually verify changes to the web interface in both English and Vietnamese.

## Pull requests

Create a branch, keep changes focused, and describe the problem, resulting behavior, and validation performed. Explain any limits on testing. Preserve source identifiers, page references, and the distinction between model explanations and verified evidence.

Never commit API keys, `.env` files, private PDFs, generated libraries, or local logs. Keep dataset provenance and third-party licensing separate from the source-code license. Do not present structural citation checks as answer-accuracy measurements or silently revise paper fingerprints.

For suspected vulnerabilities, follow SECURITY.md rather than posting sensitive details in a public issue.
