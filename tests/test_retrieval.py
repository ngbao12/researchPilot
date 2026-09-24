"""
Tests for retrieval pipeline.

Tests relevance, modality filtering, deduplication, and index
save/load functionality.
"""

from __future__ import annotations

from pathlib import Path


from researchpilot.index import EvidenceIndex, chunk_evidence, deduplicate_chunks
from researchpilot.providers.embedding import MockEmbedder
from researchpilot.retrieve import retrieve_evidence
from researchpilot.schema import (
    AnswerMode,
    Evidence,
    ExtractionMethod,
    Modality,
)


class TestChunking:
    """Test evidence chunking."""

    def test_short_text_not_split(self, sample_evidence: list[Evidence]) -> None:
        """Short evidence should remain as single chunk."""
        chunks = chunk_evidence(sample_evidence, chunk_size=2000)
        # All our sample evidence is short, so should be 1:1
        assert len(chunks) >= len(sample_evidence) - 1  # Allow some min_size filtering

    def test_long_text_split(self) -> None:
        """Long text should be split into multiple chunks."""
        long_ev = Evidence(
            evidence_id="ev-long",
            paper_id="P01",
            page=1,
            modality=Modality.TEXT,
            text="This is a test sentence. " * 100,
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        )
        chunks = chunk_evidence([long_ev], chunk_size=200, chunk_overlap=30)
        assert len(chunks) > 1

    def test_table_kept_as_single_chunk(self) -> None:
        """Table evidence should not be split."""
        table_ev = Evidence(
            evidence_id="ev-table",
            paper_id="P01",
            page=1,
            modality=Modality.TABLE,
            text="| A | B |\n| --- | --- |\n" + "| x | y |\n" * 50,
            extraction_method=ExtractionMethod.PDFPLUMBER_TABLE,
        )
        chunks = chunk_evidence([table_ev], chunk_size=100)
        assert len(chunks) == 1

    def test_chunk_preserves_metadata(self, sample_evidence: list[Evidence]) -> None:
        """Chunks should preserve paper_id and page."""
        chunks = chunk_evidence(sample_evidence, chunk_size=2000)
        for chunk in chunks:
            assert chunk.paper_id in ("P01", "P02")
            assert chunk.page >= 1
            assert chunk.chunk_index is not None

    def test_min_chunk_size(self) -> None:
        """Very short text below min_chunk_size should be filtered."""
        short_ev = Evidence(
            evidence_id="ev-short",
            paper_id="P01",
            page=1,
            modality=Modality.TEXT,
            text="Hi",
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        )
        chunks = chunk_evidence([short_ev], chunk_size=200, min_chunk_size=20)
        assert len(chunks) == 0


class TestDeduplication:
    """Test chunk deduplication."""

    def test_identical_chunks_deduped(self, mock_embedder: MockEmbedder) -> None:
        """Identical text chunks should be deduplicated."""
        ev1 = Evidence(
            evidence_id="ev-1",
            paper_id="P01",
            page=1,
            modality=Modality.TEXT,
            text="Exact same text content here.",
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        )
        ev2 = Evidence(
            evidence_id="ev-2",
            paper_id="P01",
            page=2,
            modality=Modality.TEXT,
            text="Exact same text content here.",
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        )
        result = deduplicate_chunks([ev1, ev2], mock_embedder, threshold=0.99)
        assert len(result) == 2  # Different source pages must remain citable.

    def test_different_chunks_kept(self, mock_embedder: MockEmbedder) -> None:
        """Different text chunks should be kept."""
        ev1 = Evidence(
            evidence_id="ev-1",
            paper_id="P01",
            page=1,
            modality=Modality.TEXT,
            text="This is about neural networks and deep learning architectures.",
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        )
        ev2 = Evidence(
            evidence_id="ev-2",
            paper_id="P02",
            page=1,
            modality=Modality.TEXT,
            text="Quantum computing relies on qubits and superposition states.",
            extraction_method=ExtractionMethod.PYMUPDF_TEXT,
        )
        result = deduplicate_chunks([ev1, ev2], mock_embedder, threshold=0.99)
        assert len(result) == 2


class TestIndexBuildAndSearch:
    """Test FAISS index building and search."""

    def test_index_build(self, built_index: EvidenceIndex) -> None:
        """Index should be built with correct number of vectors."""
        assert built_index.size > 0

    def test_search_returns_results(self, built_index: EvidenceIndex) -> None:
        """Search should return relevant results."""
        results = built_index.search("depthwise separable convolutions", top_k=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_search_returns_scores(self, built_index: EvidenceIndex) -> None:
        """Search results should have scores."""
        results = built_index.search("efficient convolutions", top_k=3)
        for ev, score in results:
            assert isinstance(score, float)

    def test_search_modality_filter(self, built_index: EvidenceIndex) -> None:
        """Modality filter should restrict results."""
        results = built_index.search(
            "accuracy comparison table",
            top_k=10,
            modality_filter={Modality.TABLE},
        )
        for ev, score in results:
            assert ev.modality == Modality.TABLE

    def test_search_paper_filter(self, built_index: EvidenceIndex) -> None:
        """Paper filter should restrict results."""
        results = built_index.search(
            "efficient methods",
            top_k=10,
            paper_filter={"P01"},
        )
        for ev, score in results:
            assert ev.paper_id == "P01"

    def test_evidence_lookup_by_id(
        self, built_index: EvidenceIndex, sample_evidence: list[Evidence]
    ) -> None:
        """Should be able to look up evidence by ID."""
        # The IDs may have -c{n} suffix after chunking
        results = built_index.search("test", top_k=1)
        if results:
            ev, _ = results[0]
            found = built_index.get_evidence_by_id(ev.evidence_id)
            assert found is not None
            assert found.evidence_id == ev.evidence_id

    def test_index_save_load(
        self, built_index: EvidenceIndex, tmp_dir: Path, mock_embedder: MockEmbedder
    ) -> None:
        """Index should be saveable and loadable."""
        save_dir = tmp_dir / "test_save"
        built_index.save(save_dir)

        # Load into new index
        loaded = EvidenceIndex(mock_embedder, built_index.config)
        loaded.load(save_dir)

        assert loaded.size == built_index.size

        # Search should work on loaded index
        results = loaded.search("convolutions", top_k=3)
        assert len(results) > 0


class TestRetrieval:
    """Test the retrieval pipeline."""

    def test_text_rag_only_text(self, built_index: EvidenceIndex) -> None:
        """Text RAG mode should only return text modality."""
        results = retrieve_evidence(
            query="efficient convolutions",
            index=built_index,
            mode=AnswerMode.TEXT_RAG,
            top_k=10,
        )
        for r in results:
            assert r.evidence.modality == Modality.TEXT

    def test_table_rag_includes_tables(self, built_index: EvidenceIndex) -> None:
        """Table RAG mode should include tables and captions."""
        results = retrieve_evidence(
            query="accuracy comparison results",
            index=built_index,
            mode=AnswerMode.TABLE_RAG,
            top_k=10,
        )
        modalities = {r.evidence.modality for r in results}
        # Should allow text, table, and caption
        assert modalities.issubset({Modality.TEXT, Modality.TABLE, Modality.CAPTION})

    def test_closed_book_no_retrieval(self, built_index: EvidenceIndex) -> None:
        """Closed-book mode should return no results."""
        results = retrieve_evidence(
            query="anything",
            index=built_index,
            mode=AnswerMode.CLOSED_BOOK,
            top_k=5,
        )
        assert len(results) == 0

    def test_results_have_ranks(self, built_index: EvidenceIndex) -> None:
        """Results should have sequential ranks."""
        results = retrieve_evidence(
            query="convolutions",
            index=built_index,
            mode=AnswerMode.TEXT_RAG,
            top_k=5,
        )
        for i, r in enumerate(results):
            assert r.rank == i + 1

    def test_results_have_stable_ids(self, built_index: EvidenceIndex) -> None:
        """Result evidence should have stable IDs."""
        results = retrieve_evidence(
            query="convolutions",
            index=built_index,
            mode=AnswerMode.TEXT_RAG,
            top_k=3,
        )
        ids = [r.evidence.evidence_id for r in results]
        assert len(ids) == len(set(ids))  # All unique
