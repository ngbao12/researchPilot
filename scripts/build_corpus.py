#!/usr/bin/env python3
"""
Build Corpus — Download papers and run the ingestion + indexing pipeline.

Usage:
    python scripts/build_corpus.py --manifest data/papers_manifest.json --out artifacts/
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def download_paper(url: str, output_path: Path) -> bool:
    """Download a paper PDF from arXiv or other source."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        logger.info("Already downloaded: %s", output_path)
        return True

    # Convert arXiv abstract URL to PDF URL
    pdf_url = url
    if "arxiv.org/abs/" in url:
        arxiv_id = url.split("/abs/")[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    logger.info("Downloading: %s -> %s", pdf_url, output_path)
    try:
        req = urllib.request.Request(
            pdf_url,
            headers={"User-Agent": "ResearchPilot/0.1 (research tool)"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read(50 * 1024 * 1024 + 1)
            if len(content) > 50 * 1024 * 1024 or not content.startswith(b"%PDF-"):
                raise ValueError("Download is not a PDF or exceeds 50 MB")
            with open(output_path, "wb") as f:
                f.write(content)

        size_mb = len(content) / (1024 * 1024)
        logger.info("Downloaded %.1fMB: %s", size_mb, output_path.name)
        return True

    except Exception as e:
        logger.error("Download failed: %s - %s", pdf_url, e)
        return False


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Build ResearchPilot corpus")
    parser.add_argument(
        "--manifest",
        default="data/papers_manifest.json",
        help="Path to papers manifest",
    )
    parser.add_argument(
        "--out",
        default="artifacts/current",
        help="Output base directory",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading papers (use existing files)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingestion (use existing corpus)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip indexing (use existing index)",
    )
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    from researchpilot.cli import load_config

    config = load_config(args.config)

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest_data = json.load(f)

    papers = manifest_data.get("papers", [])
    output_dir = Path(args.out)

    # 1. Download papers
    if not args.skip_download:
        logger.info("=== Phase 1: Downloading %d papers ===", len(papers))
        for paper in papers:
            from researchpilot.ingest import sanitize_path

            output_path = sanitize_path(paper["local_path"])
            success = download_paper(paper["source_url"], output_path)
            if not success:
                raise SystemExit(f"Download failed: {paper['paper_id']}")
    else:
        logger.info("Skipping download phase")

    # 2. Ingest
    if not args.skip_ingest:
        logger.info("=== Phase 2: Ingesting corpus ===")
        try:
            from researchpilot.ingest import ingest_corpus
            from researchpilot.schema import CorpusManifest, PaperMeta

            corpus_manifest = CorpusManifest(
                papers=[PaperMeta(**p) for p in papers],
                domain=manifest_data.get("domain", ""),
                description=manifest_data.get("description", ""),
            )

            corpus = ingest_corpus(
                manifest=corpus_manifest,
                output_dir=output_dir / "corpus",
                max_pages=config.get("ingest", {}).get("max_pages", 200),
                max_file_size_mb=config.get("ingest", {}).get("max_file_size_mb", 50),
                extract_tables_flag=config.get("ingest", {}).get("extract_tables", True),
                extract_figures_flag=config.get("ingest", {}).get("extract_figures", True),
                extract_captions_flag=config.get("ingest", {}).get("extract_captions", True),
            )
            if any(not ext.evidence for ext in corpus.extractions):
                raise ValueError("One or more papers failed extraction; inspect corpus.json")
            logger.info(
                "Ingestion complete: %d papers, %d evidence items",
                len(papers),
                len(corpus.all_evidence),
            )
        except Exception as e:
            logger.error("Ingestion failed: %s", e)
            sys.exit(1)
    else:
        logger.info("Skipping ingestion phase")

    # 3. Index
    if not args.skip_index:
        logger.info("=== Phase 3: Building index ===")
        try:
            from researchpilot.index import build_index
            from researchpilot.schema import CorpusData, IndexConfig

            corpus_path = output_dir / "corpus" / "corpus.json"
            with open(corpus_path) as f:
                corpus_data = CorpusData.model_validate_json(f.read())

            index_config = IndexConfig(**config.get("index", {}))
            evidence_index = build_index(
                corpus=corpus_data,
                config=index_config,
                output_dir=output_dir / "index",
            )
            logger.info("Index built: %d vectors", evidence_index.size)
        except Exception as e:
            logger.error("Indexing failed: %s", e)
            sys.exit(1)
    else:
        logger.info("Skipping indexing phase")

    logger.info("=== Corpus build complete ===")
    logger.info("Corpus: %s/corpus/", output_dir)
    logger.info("Index:  %s/index/", output_dir)


if __name__ == "__main__":
    main()
