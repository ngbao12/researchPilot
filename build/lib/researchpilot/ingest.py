"""
ResearchPilot Ingestion Pipeline.

Extracts text blocks, tables, figure crops, and captions from PDFs
with page-level provenance. Uses PyMuPDF for text/images and pdfplumber
for table extraction.

Security: bounds file size/page count, sanitizes paths, treats PDF text
as data (never instructions).
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
import time
from pathlib import Path

from researchpilot.schema import (
    CorpusData,
    CorpusManifest,
    Evidence,
    ExtractionMethod,
    ExtractionResult,
    Modality,
    PaperMeta,
)

logger = logging.getLogger(__name__)

# Security bounds
MAX_FILE_SIZE_MB = 50
MAX_PAGES = 200
ALLOWED_EXTENSIONS = {".pdf"}


def sanitize_path(path: str) -> Path:
    """Sanitize and validate a file path."""
    # Prevent path traversal
    if ".." in Path(path).parts:
        raise ValueError(f"Path traversal detected: {path}")
    return Path(path).resolve()


def validate_pdf(path: Path, max_size_mb: float = MAX_FILE_SIZE_MB) -> None:
    """Validate PDF file before processing."""
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file format: {path.suffix}")
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File too large: {size_mb:.1f}MB > {max_size_mb}MB limit")


def extract_text_blocks(
    pdf_path: Path,
    paper_id: str,
    source_url: str = "",
    max_pages: int = MAX_PAGES,
) -> tuple[list[Evidence], list[str]]:
    """
    Extract text blocks from PDF using PyMuPDF with page provenance.

    Returns:
        Tuple of (evidence_list, error_list).
    """
    import fitz  # PyMuPDF

    evidence: list[Evidence] = []
    errors: list[str] = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        errors.append(f"Failed to open PDF: {e}")
        return evidence, errors

    page_count = min(len(doc), max_pages)
    if len(doc) > max_pages:
        errors.append(f"PDF truncated: {len(doc)} pages > {max_pages} limit")

    section = ""
    for page_num in range(page_count):
        try:
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for block_idx, block in enumerate(blocks):
                if block.get("type") != 0:  # 0 = text block
                    continue

                # Concatenate lines in the block
                text_lines = []
                for line in block.get("lines", []):
                    spans_text = " ".join(span.get("text", "") for span in line.get("spans", []))
                    if spans_text.strip():
                        text_lines.append(spans_text.strip())

                text = unicodedata.normalize("NFKC", "\n".join(text_lines).strip())
                text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
                first_line = text.split("\n", 1)[0]
                if len(text) < 100 and re.match(
                    r"^(?:\d+(?:\.\d+)*\.?\s+[A-Z]|Abstract$|References$|Conclusion)", first_line
                ):
                    section = text
                # Captions are stored separately so the no-caption ablation is meaningful.
                if re.match(r"^(Figure|Fig\.|Table|Tab\.)\s*\d+[.:]", text, re.I):
                    continue
                if not text or len(text) < 10:  # Skip very short fragments
                    continue

                bbox = block.get("bbox", (0, 0, 0, 0))
                ev = Evidence(
                    evidence_id=f"ev-{paper_id}-p{page_num + 1}-t{block_idx}",
                    paper_id=paper_id,
                    source_url=source_url,
                    page=page_num + 1,
                    modality=Modality.TEXT,
                    section=section,
                    text=text,
                    bbox=tuple(bbox) if bbox else None,
                    extraction_method=ExtractionMethod.PYMUPDF_TEXT,
                )
                evidence.append(ev)

        except Exception as e:
            errors.append(f"Page {page_num + 1} text extraction error: {e}")

    doc.close()
    logger.info(
        "Extracted %d text blocks from %s (%d pages)",
        len(evidence),
        paper_id,
        page_count,
    )
    return evidence, errors


def extract_tables(
    pdf_path: Path,
    paper_id: str,
    source_url: str = "",
    max_pages: int = MAX_PAGES,
) -> tuple[list[Evidence], list[str]]:
    """
    Extract tables from PDF using pdfplumber, output as Markdown.

    Returns:
        Tuple of (evidence_list, error_list).
    """
    import pdfplumber

    evidence: list[Evidence] = []
    errors: list[str] = []

    try:
        pdf = pdfplumber.open(str(pdf_path))
    except Exception as e:
        errors.append(f"Failed to open PDF for table extraction: {e}")
        return evidence, errors

    page_count = min(len(pdf.pages), max_pages)

    for page_idx in range(page_count):
        try:
            page = pdf.pages[page_idx]
            tables = page.find_tables()

            for table_idx, table_object in enumerate(tables):
                table = table_object.extract()
                if not table or len(table) < 2:
                    continue
                cells = [str(cell or "").strip() for row in table for cell in row]
                nonempty = sum(bool(cell) for cell in cells)
                populated_rows = sum(
                    sum(bool(str(c or "").strip()) for c in row) >= 2 for row in table
                )
                if not cells or nonempty / len(cells) < 0.45 or populated_rows < 2:
                    errors.append(
                        f"Page {page_idx + 1} table {table_idx}: rejected sparse/grid artifact"
                    )
                    continue

                # Convert to Markdown table
                md_lines = []
                for row_idx, row in enumerate(table):
                    cells = [str(cell or "").strip() for cell in row]
                    md_lines.append("| " + " | ".join(cells) + " |")
                    if row_idx == 0:
                        md_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")

                md_text = "\n".join(md_lines)
                if not md_text.strip():
                    continue

                ev = Evidence(
                    evidence_id=f"ev-{paper_id}-p{page_idx + 1}-tab{table_idx}",
                    paper_id=paper_id,
                    source_url=source_url,
                    page=page_idx + 1,
                    modality=Modality.TABLE,
                    text=md_text,
                    bbox=tuple(table_object.bbox),
                    extraction_method=ExtractionMethod.PDFPLUMBER_TABLE,
                )
                evidence.append(ev)

        except Exception as e:
            errors.append(f"Page {page_idx + 1} table extraction error: {e}")

    pdf.close()
    logger.info(
        "Extracted %d tables from %s (%d pages)",
        len(evidence),
        paper_id,
        page_count,
    )
    return evidence, errors


def extract_figures(
    pdf_path: Path,
    paper_id: str,
    output_dir: Path,
    source_url: str = "",
    max_pages: int = MAX_PAGES,
) -> tuple[list[Evidence], list[str]]:
    """
    Extract figure crops and captions from PDF.

    Saves figure crops as PNG images and identifies captions using heuristics.

    Returns:
        Tuple of (evidence_list, error_list).
    """
    import fitz  # PyMuPDF

    evidence: list[Evidence] = []
    errors: list[str] = []
    if not re.fullmatch(r"[A-Za-z0-9_-]+", paper_id):
        raise ValueError("Unsafe paper ID")
    figures_dir = output_dir / paper_id / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        errors.append(f"Failed to open PDF for figure extraction: {e}")
        return evidence, errors

    page_count = min(len(doc), max_pages)

    for page_num in range(page_count):
        try:
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image["image"]
                    image_ext = base_image.get("ext", "png")

                    # Skip very small images (likely icons/artifacts)
                    if len(image_bytes) < 5000:
                        continue

                    # Save figure crop
                    fig_filename = f"fig-p{page_num + 1}-{img_idx}.{image_ext}"
                    fig_path = figures_dir / fig_filename
                    with open(fig_path, "wb") as f:
                        f.write(image_bytes)

                    ev = Evidence(
                        evidence_id=f"ev-{paper_id}-p{page_num + 1}-fig{img_idx}",
                        paper_id=paper_id,
                        source_url=source_url,
                        page=page_num + 1,
                        modality=Modality.FIGURE,
                        text="",  # Will be populated with caption if found
                        crop_path=str(fig_path),
                        extraction_method=ExtractionMethod.PYMUPDF_IMAGE,
                    )
                    evidence.append(ev)

                except Exception as e:
                    errors.append(f"Page {page_num + 1} image {img_idx} extraction error: {e}")

        except Exception as e:
            errors.append(f"Page {page_num + 1} figure extraction error: {e}")

    doc.close()
    logger.info(
        "Extracted %d figures from %s (%d pages)",
        len(evidence),
        paper_id,
        page_count,
    )
    return evidence, errors


def extract_captions(
    pdf_path: Path,
    paper_id: str,
    source_url: str = "",
    max_pages: int = MAX_PAGES,
) -> tuple[list[Evidence], list[str]]:
    """
    Extract figure and table captions using text heuristics.

    Looks for patterns like "Figure 1:", "Table 2:", "Fig. 3." etc.

    Returns:
        Tuple of (evidence_list, error_list).
    """
    import fitz  # PyMuPDF

    evidence: list[Evidence] = []
    errors: list[str] = []

    caption_pattern = re.compile(
        r"^(Figure|Fig\.|Table|Tab\.)\s*\d+[\.:]\s*(.+)",
        re.IGNORECASE | re.MULTILINE,
    )

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        errors.append(f"Failed to open PDF for caption extraction: {e}")
        return evidence, errors

    page_count = min(len(doc), max_pages)

    for page_num in range(page_count):
        try:
            page = doc[page_num]
            for block_idx, block in enumerate(page.get_text("blocks")):
                text = unicodedata.normalize("NFKC", block[4]).strip()
                if not caption_pattern.match(text):
                    continue
                evidence.append(
                    Evidence(
                        evidence_id=f"ev-{paper_id}-p{page_num + 1}-cap{block_idx}",
                        paper_id=paper_id,
                        source_url=source_url,
                        page=page_num + 1,
                        modality=Modality.CAPTION,
                        text=text,
                        bbox=tuple(block[:4]),
                        extraction_method=ExtractionMethod.CAPTION_HEURISTIC,
                    )
                )

        except Exception as e:
            errors.append(f"Page {page_num + 1} caption extraction error: {e}")

    doc.close()
    logger.info(
        "Extracted %d captions from %s (%d pages)",
        len(evidence),
        paper_id,
        page_count,
    )
    return evidence, errors


def ingest_paper(
    paper: PaperMeta,
    output_dir: Path,
    extract_tables_flag: bool = True,
    extract_figures_flag: bool = True,
    extract_captions_flag: bool = True,
    max_pages: int = MAX_PAGES,
    max_file_size_mb: float = MAX_FILE_SIZE_MB,
) -> ExtractionResult:
    """
    Ingest a single paper: extract all content types with provenance.

    Args:
        paper: Paper metadata.
        output_dir: Directory to save extraction artifacts.
        extract_tables_flag: Whether to extract tables.
        extract_figures_flag: Whether to extract figure crops.
        extract_captions_flag: Whether to extract captions.
        max_pages: Maximum pages to process.
        max_file_size_mb: Maximum file size in MB.

    Returns:
        ExtractionResult with all evidence and errors.
    """
    start = time.perf_counter()
    all_evidence: list[Evidence] = []
    all_errors: list[str] = []

    try:
        pdf_path = sanitize_path(paper.local_path)
        validate_pdf(pdf_path, max_file_size_mb)
        if paper.sha256 and hashlib.sha256(pdf_path.read_bytes()).hexdigest() != paper.sha256:
            raise ValueError("Source PDF checksum differs from manifest")
    except (FileNotFoundError, ValueError) as e:
        return ExtractionResult(
            paper_id=paper.paper_id,
            errors=[str(e)],
        )

    import fitz

    try:
        with fitz.open(pdf_path) as doc:
            actual_pages = len(doc)
    except Exception as exc:
        return ExtractionResult(paper_id=paper.paper_id, errors=[f"Invalid PDF: {exc}"])

    # 1. Text blocks
    text_ev, text_err = extract_text_blocks(pdf_path, paper.paper_id, paper.source_url, max_pages)
    all_evidence.extend(text_ev)
    all_errors.extend(text_err)

    # 2. Tables
    table_count = 0
    if extract_tables_flag:
        table_ev, table_err = extract_tables(pdf_path, paper.paper_id, paper.source_url, max_pages)
        all_evidence.extend(table_ev)
        all_errors.extend(table_err)
        table_count = len(table_ev)

    # 3. Figures
    fig_count = 0
    if extract_figures_flag:
        fig_ev, fig_err = extract_figures(
            pdf_path, paper.paper_id, output_dir, paper.source_url, max_pages
        )
        all_evidence.extend(fig_ev)
        all_errors.extend(fig_err)
        fig_count = len(fig_ev)

    # 4. Captions
    if extract_captions_flag:
        cap_ev, cap_err = extract_captions(pdf_path, paper.paper_id, paper.source_url, max_pages)
        all_evidence.extend(cap_ev)
        all_errors.extend(cap_err)

    elapsed_ms = (time.perf_counter() - start) * 1000

    result = ExtractionResult(
        paper_id=paper.paper_id,
        evidence=all_evidence,
        errors=all_errors,
        page_count=min(actual_pages, max_pages),
        text_blocks=len(text_ev),
        tables=table_count,
        figures=fig_count,
        extraction_time_ms=elapsed_ms,
    )

    logger.info(
        "Ingested %s: %d evidence items (%d text, %d tables, %d figures), %d errors, %.0fms",
        paper.paper_id,
        len(all_evidence),
        len(text_ev),
        table_count,
        fig_count,
        len(all_errors),
        elapsed_ms,
    )

    return result


def ingest_corpus(
    manifest: CorpusManifest,
    output_dir: Path,
    extract_tables_flag: bool = True,
    extract_figures_flag: bool = True,
    extract_captions_flag: bool = True,
    max_pages: int = MAX_PAGES,
    max_file_size_mb: float = MAX_FILE_SIZE_MB,
) -> CorpusData:
    """
    Ingest all papers in a corpus manifest.

    Args:
        manifest: Corpus manifest with paper metadata.
        output_dir: Base directory for extraction artifacts.

    Returns:
        CorpusData with all extractions.
    """
    output_dir = Path(output_dir)
    if (output_dir / "corpus.json").exists():
        raise ValueError("Corpus exists; choose a new output directory to preserve the snapshot")
    output_dir.mkdir(parents=True, exist_ok=True)

    extractions: list[ExtractionResult] = []
    all_evidence: list[Evidence] = []

    for paper in manifest.papers:
        logger.info("Ingesting paper: %s (%s)", paper.paper_id, paper.title)
        result = ingest_paper(
            paper,
            output_dir,
            extract_tables_flag=extract_tables_flag,
            extract_figures_flag=extract_figures_flag,
            extract_captions_flag=extract_captions_flag,
            max_pages=max_pages,
            max_file_size_mb=max_file_size_mb,
        )
        extractions.append(result)
        all_evidence.extend(result.evidence)

    corpus = CorpusData(
        manifest=manifest,
        extractions=extractions,
        all_evidence=all_evidence,
    )

    # Save corpus data
    corpus_file = output_dir / "corpus.json"
    with open(corpus_file, "w") as f:
        f.write(corpus.model_dump_json(indent=2))

    logger.info(
        "Corpus ingestion complete: %d papers, %d total evidence items",
        len(manifest.papers),
        len(all_evidence),
    )

    return corpus
