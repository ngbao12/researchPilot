"""
ResearchPilot Schema — Pydantic data models for all data contracts.

Defines Evidence, Answer, Paper, Question, BenchmarkResult, CorpusManifest,
and IndexConfig models with JSON schema validation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ──────────────────────────────────────────────────────────────────────


class Modality(str, Enum):
    """Evidence modality types."""

    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"


class ExtractionMethod(str, Enum):
    """How evidence was extracted from the PDF."""

    PYMUPDF_TEXT = "pymupdf_text"
    PDFPLUMBER_TABLE = "pdfplumber_table"
    PYMUPDF_IMAGE = "pymupdf_image"
    CAPTION_HEURISTIC = "caption_heuristic"
    OCR = "ocr"


class AnswerMode(str, Enum):
    """Retrieval/generation modes for benchmarking."""

    CLOSED_BOOK = "closed-book"
    TEXT_RAG = "text-rag"
    TABLE_RAG = "table-rag"
    VLM_RAG = "vlm-rag"
    CAPTION_RAG = "caption-rag"


class Difficulty(str, Enum):
    """Question difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ── Core Data Models ──────────────────────────────────────────────────────────


class Evidence(BaseModel):
    """
    A single piece of evidence extracted from a paper.
    Maps to a specific location in the source document.
    """

    evidence_id: str = Field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:8]}")
    paper_id: str
    source_url: str = ""
    page: int = Field(ge=1, description="1-indexed page number")
    section: str = ""
    modality: Modality
    text: str = ""
    crop_path: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    extraction_method: ExtractionMethod
    chunk_index: int | None = None

    @field_validator("text")
    @classmethod
    def text_not_empty_for_text_modality(cls, v: str, info: Any) -> str:
        """Text modality evidence must have non-empty text."""
        if info.data.get("modality") == Modality.TEXT and not v.strip():
            raise ValueError("Text evidence must have non-empty text content")
        return v


class Citation(BaseModel):
    """A citation reference in an answer."""

    paper_id: str
    page: int = Field(ge=1)
    evidence_id: str


class Answer(BaseModel):
    """
    Generated answer with citations, metadata, and audit trail.
    """

    answer: str
    abstained: bool = False
    citations: list[Citation] = Field(default_factory=list)
    retrieved: list[str] = Field(
        default_factory=list,
        description="List of evidence_ids that were retrieved",
    )
    mode: AnswerMode
    model_id: str = ""
    model_version: str = ""
    prompt_template: str = ""
    temperature: float = 0.0
    seed: int | None = None
    latency_ms: float = 0.0
    usage: dict[str, int] = Field(
        default_factory=dict,
        description="Token usage: prompt_tokens, completion_tokens, total_tokens",
    )
    warnings: list[str] = Field(default_factory=list)
    raw_response: str = ""
    retrieved_evidence: list[RetrievalResult] = Field(default_factory=list)
    evidence_terms: dict[str, list[str]] = Field(default_factory=dict)
    support_quotes: dict[str, list[str]] = Field(default_factory=dict)
    evidence_support: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    retrieval_method: str = "lexical"
    limitations: list[str] = Field(default_factory=list)
    prompt: str = ""
    system_prompt: str = ""
    usage_kind: str = "measured"
    retrieval_latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RetrievalResult(BaseModel):
    """A single retrieval result with score."""

    evidence: Evidence
    score: float
    rank: int


# ── Paper & Corpus ─────────────────────────────────────────────────────────────


class PaperMeta(BaseModel):
    """Metadata for a single paper in the corpus."""

    paper_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_url: str
    local_path: str = ""
    license: str = "unknown"
    license_url: str = ""
    license_checked_at: str = ""
    sha256: str = ""
    pages: int | None = None
    domain: str = ""
    notes: str = ""


class CorpusManifest(BaseModel):
    """Immutable manifest of all papers in the corpus."""

    manifest_id: str = Field(default_factory=lambda: f"manifest-{uuid.uuid4().hex[:8]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    papers: list[PaperMeta]
    domain: str = ""
    description: str = ""

    @model_validator(mode="after")
    def unique_papers(self):
        ids = [p.paper_id for p in self.papers]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Manifest requires unique, nonempty papers")
        return self


class ExtractionResult(BaseModel):
    """Result of extracting content from a single paper."""

    paper_id: str
    evidence: list[Evidence] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    page_count: int = 0
    text_blocks: int = 0
    tables: int = 0
    figures: int = 0
    extraction_time_ms: float = 0.0


class CorpusData(BaseModel):
    """Complete extracted corpus data."""

    manifest: CorpusManifest
    extractions: list[ExtractionResult] = Field(default_factory=list)
    all_evidence: list[Evidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Index Config ───────────────────────────────────────────────────────────────


class IndexConfig(BaseModel):
    """Configuration for the FAISS index."""

    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=32, ge=0)
    min_chunk_size: int = Field(default=50, gt=0)
    embedding_model: str = "lexical-hash-v1"
    embedding_provider: str = "lexical"
    embedding_dim: int = Field(default=4096, gt=0)
    index_type: str = "faiss_flat"
    dedup_threshold: float = Field(default=0.95, ge=0, le=1)
    batch_size: int = Field(default=32, gt=0)

    @model_validator(mode="after")
    def valid_chunking(self):
        if self.chunk_overlap >= self.chunk_size or self.min_chunk_size > self.chunk_size:
            raise ValueError("Require overlap < chunk_size and min_chunk_size <= chunk_size")
        if self.index_type != "faiss_flat":
            raise ValueError("Only faiss_flat is implemented")
        return self


# ── Benchmark & Evaluation ────────────────────────────────────────────────────


class GoldEvidence(BaseModel):
    """Gold-standard evidence reference for a benchmark question."""

    paper_id: str
    page: int
    evidence_id: str | None = None
    modality: Modality
    excerpt: str = ""


class BenchmarkQuestion(BaseModel):
    """A single benchmark question with gold answer and evidence."""

    question_id: str
    question: str
    source_papers: list[str]
    gold_answer: str
    gold_evidence: list[GoldEvidence]
    modality: Modality
    difficulty: Difficulty
    answerable: bool = True
    category: str = ""
    annotator_notes: str = ""
    held_out: bool = False
    verification_status: str = "unverified"


class BenchmarkPrediction(BaseModel):
    """A single prediction from the system for a benchmark question."""

    question_id: str
    answer: Answer
    config: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BenchmarkRun(BaseModel):
    """A complete benchmark run with all predictions."""

    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    mode: AnswerMode
    model_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    predictions: list[BenchmarkPrediction] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class EvaluationMetrics(BaseModel):
    """Evaluation metrics for a benchmark run."""

    run_id: str
    mode: AnswerMode
    total_questions: int = 0
    correct: int = 0
    incorrect: int = 0
    abstained: int = 0
    accuracy: float = 0.0
    evidence_recall_at_k: float = 0.0
    citation_precision: float = 0.0
    citation_support_rate: float = 0.0
    abstention_precision: float = 0.0
    abstention_recall: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    per_category: dict[str, dict[str, float]] = Field(default_factory=dict)
    per_modality: dict[str, dict[str, float]] = Field(default_factory=dict)


class ComparisonResult(BaseModel):
    """Result of comparing answers about two papers."""

    question: str
    paper_a_id: str
    paper_b_id: str
    paper_a_evidence: list[RetrievalResult] = Field(default_factory=list)
    paper_b_evidence: list[RetrievalResult] = Field(default_factory=list)
    answer: Answer | None = None
    unsupported_flags: list[str] = Field(default_factory=list)


Answer.model_rebuild()
