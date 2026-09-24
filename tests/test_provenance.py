"""
Tests for page-level provenance tracking.

Ensures that every evidence item has correct page numbers,
paper IDs, and extraction metadata.
"""

from __future__ import annotations

from researchpilot.schema import Evidence, ExtractionMethod, Modality


class TestProvenance:
    """Test suite for evidence provenance."""

    def test_evidence_has_page_number(self, sample_evidence: list[Evidence]) -> None:
        """Every evidence item must have a valid page number."""
        for ev in sample_evidence:
            assert ev.page >= 1, f"Evidence {ev.evidence_id} has invalid page: {ev.page}"

    def test_evidence_has_paper_id(self, sample_evidence: list[Evidence]) -> None:
        """Every evidence item must have a paper_id."""
        for ev in sample_evidence:
            assert ev.paper_id, f"Evidence {ev.evidence_id} has empty paper_id"

    def test_evidence_has_extraction_method(self, sample_evidence: list[Evidence]) -> None:
        """Every evidence item must record its extraction method."""
        for ev in sample_evidence:
            assert isinstance(ev.extraction_method, ExtractionMethod), (
                f"Evidence {ev.evidence_id} has invalid extraction_method"
            )

    def test_evidence_has_modality(self, sample_evidence: list[Evidence]) -> None:
        """Every evidence item must have a modality tag."""
        for ev in sample_evidence:
            assert isinstance(ev.modality, Modality), (
                f"Evidence {ev.evidence_id} has invalid modality"
            )

    def test_evidence_id_uniqueness(self, sample_evidence: list[Evidence]) -> None:
        """Evidence IDs must be unique within a corpus."""
        ids = [ev.evidence_id for ev in sample_evidence]
        assert len(ids) == len(set(ids)), "Duplicate evidence IDs found"

    def test_evidence_id_contains_paper_id(self, sample_evidence: list[Evidence]) -> None:
        """Evidence IDs should encode the paper ID for traceability."""
        for ev in sample_evidence:
            assert ev.paper_id in ev.evidence_id, (
                f"Evidence ID {ev.evidence_id} doesn't contain paper_id {ev.paper_id}"
            )

    def test_evidence_id_contains_page(self, sample_evidence: list[Evidence]) -> None:
        """Evidence IDs should encode the page number for traceability."""
        for ev in sample_evidence:
            assert f"p{ev.page}" in ev.evidence_id, (
                f"Evidence ID {ev.evidence_id} doesn't contain page p{ev.page}"
            )

    def test_text_evidence_has_content(self, sample_evidence: list[Evidence]) -> None:
        """Text evidence must have non-empty text content."""
        for ev in sample_evidence:
            if ev.modality == Modality.TEXT:
                assert ev.text.strip(), f"Text evidence {ev.evidence_id} has empty text"

    def test_table_evidence_has_structure(self, sample_evidence: list[Evidence]) -> None:
        """Table evidence should contain Markdown table markers."""
        for ev in sample_evidence:
            if ev.modality == Modality.TABLE:
                assert "|" in ev.text, (
                    f"Table evidence {ev.evidence_id} missing Markdown table format"
                )

    def test_caption_evidence_pattern(self, sample_evidence: list[Evidence]) -> None:
        """Caption evidence should match Figure/Table caption patterns."""
        for ev in sample_evidence:
            if ev.modality == Modality.CAPTION:
                text_lower = ev.text.lower()
                assert any(kw in text_lower for kw in ["figure", "fig.", "table", "tab."]), (
                    f"Caption {ev.evidence_id} doesn't look like a caption: {ev.text[:50]}"
                )

    def test_corpus_extraction_counts(self, sample_corpus) -> None:
        """Extraction results should have correct content type counts."""
        for ext in sample_corpus.extractions:
            text_count = sum(1 for e in ext.evidence if e.modality == Modality.TEXT)
            table_count = sum(1 for e in ext.evidence if e.modality == Modality.TABLE)
            assert ext.text_blocks == text_count, (
                f"Paper {ext.paper_id}: text_blocks count mismatch"
            )
            assert ext.tables == table_count, f"Paper {ext.paper_id}: tables count mismatch"

    def test_evidence_page_within_document(self, sample_corpus) -> None:
        """Evidence page numbers should not exceed document page count."""
        for ext in sample_corpus.extractions:
            for ev in ext.evidence:
                assert ev.page <= ext.page_count, (
                    f"Evidence {ev.evidence_id} page {ev.page} exceeds "
                    f"document page count {ext.page_count}"
                )
