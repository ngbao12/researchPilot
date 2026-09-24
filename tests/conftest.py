"""
Test fixtures for ResearchPilot.

Provides synthetic two-page PDF documents and mock providers
so tests don't require external API access or real PDFs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from researchpilot.providers.embedding import MockEmbedder
from researchpilot.providers.llm import MockGenerator
from researchpilot.schema import (
    CorpusData,
    CorpusManifest,
    Evidence,
    ExtractionMethod,
    ExtractionResult,
    IndexConfig,
    Modality,
    PaperMeta,
)


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    """Create a deterministic mock embedder."""
    return MockEmbedder(dimension=384)


@pytest.fixture
def mock_generator() -> MockGenerator:
    """Create a deterministic mock generator."""
    return MockGenerator(default_paper_id="P01")


@pytest.fixture
def index_config() -> IndexConfig:
    """Create default index config for tests."""
    return IndexConfig(
        chunk_size=256,
        chunk_overlap=32,
        min_chunk_size=20,
        embedding_model="mock",
        embedding_provider="mock",
        embedding_dim=384,
        dedup_threshold=0.95,
    )


@pytest.fixture
def sample_evidence() -> list[Evidence]:
    """Create sample evidence items for testing."""
    return [
        Evidence(
            evidence_id="ev-P01-p1-t0",
            paper_id="P01",
            source_url="https://arxiv.org/abs/1234.5678",
            page=1,
            section="Introduction",
            modality=Modality.TEXT,
            text=(
                "We propose a novel method for efficient image classification "
                "using depthwise separable convolutions. This approach reduces "
                "computational cost by a factor of 8-9x compared to standard "
                "convolutions while maintaining comparable accuracy."
            ),
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        ),
        Evidence(
            evidence_id="ev-P01-p2-t0",
            paper_id="P01",
            source_url="https://arxiv.org/abs/1234.5678",
            page=2,
            section="Methods",
            modality=Modality.TEXT,
            text=(
                "The depthwise separable convolution factorizes a standard "
                "convolution into a depthwise convolution followed by a 1x1 "
                "pointwise convolution. This decomposition significantly "
                "reduces the number of parameters and computations."
            ),
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        ),
        Evidence(
            evidence_id="ev-P01-p2-tab0",
            paper_id="P01",
            source_url="https://arxiv.org/abs/1234.5678",
            page=2,
            section="Results",
            modality=Modality.TABLE,
            text=(
                "| Model | Top-1 Acc | FLOPs | Params |\n"
                "| --- | --- | --- | --- |\n"
                "| Standard CNN | 71.5% | 1.2B | 4.2M |\n"
                "| MobileNet | 70.6% | 569M | 3.4M |"
            ),
            extraction_method=ExtractionMethod.PDFPLUMBER_TABLE,
        ),
        Evidence(
            evidence_id="ev-P01-p1-cap0",
            paper_id="P01",
            source_url="https://arxiv.org/abs/1234.5678",
            page=1,
            modality=Modality.CAPTION,
            text="Figure 1: Architecture of the depthwise separable convolution block.",
            extraction_method=ExtractionMethod.CAPTION_HEURISTIC,
        ),
        Evidence(
            evidence_id="ev-P02-p1-t0",
            paper_id="P02",
            source_url="https://arxiv.org/abs/2345.6789",
            page=1,
            section="Introduction",
            modality=Modality.TEXT,
            text=(
                "We propose a compound scaling method that uniformly scales "
                "network width, depth, and resolution. Unlike conventional "
                "practice of scaling only one dimension, our compound scaling "
                "achieves better accuracy and efficiency."
            ),
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        ),
        Evidence(
            evidence_id="ev-P02-p3-tab0",
            paper_id="P02",
            source_url="https://arxiv.org/abs/2345.6789",
            page=3,
            section="Results",
            modality=Modality.TABLE,
            text=(
                "| Model | Top-1 Acc | FLOPs | Params |\n"
                "| --- | --- | --- | --- |\n"
                "| EfficientNet-B0 | 77.1% | 0.39B | 5.3M |\n"
                "| EfficientNet-B7 | 84.3% | 37B | 66M |"
            ),
            extraction_method=ExtractionMethod.PDFPLUMBER_TABLE,
        ),
    ]


@pytest.fixture
def sample_papers() -> list[PaperMeta]:
    """Create sample paper metadata."""
    return [
        PaperMeta(
            paper_id="P01",
            title="Test Paper on Efficient Convolutions",
            authors=["Author A", "Author B"],
            year=2017,
            source_url="https://arxiv.org/abs/1234.5678",
            license="CC-BY-4.0",
            domain="efficient_vision_models",
        ),
        PaperMeta(
            paper_id="P02",
            title="Test Paper on Model Scaling",
            authors=["Author C"],
            year=2019,
            source_url="https://arxiv.org/abs/2345.6789",
            license="CC-BY-4.0",
            domain="efficient_vision_models",
        ),
    ]


@pytest.fixture
def sample_corpus(
    sample_papers: list[PaperMeta],
    sample_evidence: list[Evidence],
) -> CorpusData:
    """Create a sample corpus for testing."""
    manifest = CorpusManifest(
        papers=sample_papers,
        domain="efficient_vision_models",
        description="Test corpus",
    )

    p01_evidence = [e for e in sample_evidence if e.paper_id == "P01"]
    p02_evidence = [e for e in sample_evidence if e.paper_id == "P02"]

    extractions = [
        ExtractionResult(
            paper_id="P01",
            evidence=p01_evidence,
            page_count=2,
            text_blocks=2,
            tables=1,
            figures=0,
        ),
        ExtractionResult(
            paper_id="P02",
            evidence=p02_evidence,
            page_count=3,
            text_blocks=1,
            tables=1,
            figures=0,
        ),
    ]

    return CorpusData(
        manifest=manifest,
        extractions=extractions,
        all_evidence=sample_evidence,
    )


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def built_index(
    sample_corpus: CorpusData,
    mock_embedder: MockEmbedder,
    index_config: IndexConfig,
    tmp_dir: Path,
):
    """Build and return a test index."""
    from researchpilot.index import build_index

    return build_index(
        corpus=sample_corpus,
        config=index_config,
        output_dir=tmp_dir / "index",
        embedder=mock_embedder,
    )


def create_synthetic_pdf(output_path: Path) -> None:
    """
    Create a minimal synthetic two-page PDF for testing.
    Uses PyMuPDF (fitz) to generate a PDF with known content.
    """
    try:
        import fitz

        doc = fitz.open()

        # Page 1
        page1 = doc.new_page(width=612, height=792)
        page1.insert_text(
            (72, 72),
            "Test Paper: Efficient Methods\n\n"
            "Abstract: This paper proposes efficient methods for "
            "neural network inference. We demonstrate that depthwise "
            "separable convolutions reduce computation by 8x.\n\n"
            "Figure 1: Architecture overview of the proposed method.",
            fontsize=11,
        )

        # Page 2
        page2 = doc.new_page(width=612, height=792)
        page2.insert_text(
            (72, 72),
            "Results\n\n"
            "Our method achieves 70.6% top-1 accuracy on ImageNet "
            "with only 569M FLOPs, compared to 71.5% with 1.2B FLOPs "
            "for the baseline.\n\n"
            "Table 1: Comparison of computational costs.\n"
            "Model | Accuracy | FLOPs\n"
            "Ours  | 70.6%    | 569M\n"
            "Base  | 71.5%    | 1.2B",
            fontsize=11,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        doc.close()

    except ImportError:
        # If PyMuPDF is not available, create a minimal PDF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Minimal valid PDF
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer<</Root 1 0 R/Size 4>>\n"
            b"startxref\n190\n%%EOF"
        )
        with open(output_path, "wb") as f:
            f.write(pdf_content)
