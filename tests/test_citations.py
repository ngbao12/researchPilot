"""
Tests for citation parsing, validation, and metrics.

Ensures citations map to stored evidence, catches missing/wrong-page
citations, and computes metrics correctly.
"""

from __future__ import annotations


from researchpilot.citations import (
    abstention_quality,
    citation_precision,
    evidence_recall_at_k,
    validate_answer_citations,
)
from researchpilot.generate import parse_citations, validate_citations
from researchpilot.schema import (
    Answer,
    AnswerMode,
    BenchmarkQuestion,
    Citation,
    Difficulty,
    Evidence,
    ExtractionMethod,
    GoldEvidence,
    Modality,
    RetrievalResult,
)


class TestCitationParsing:
    """Test citation parsing from answer text."""

    def test_parse_single_citation(self) -> None:
        """Parse a single [paper_id, p.N, evidence_id] citation."""
        text = "The method uses depthwise convolutions [P01, p.3, ev-P01-p3-t0]."
        citations = parse_citations(text)
        assert len(citations) == 1
        assert citations[0].paper_id == "P01"
        assert citations[0].page == 3
        assert citations[0].evidence_id == "ev-P01-p3-t0"

    def test_parse_multiple_citations(self) -> None:
        """Parse multiple citations in one answer."""
        text = (
            "The model achieves 70.6% accuracy [P01, p.2, ev-P01-p2-tab0]. "
            "It uses depthwise separable convolutions [P01, p.1, ev-P01-p1-t0], "
            "which were proposed in [P02, p.1, ev-P02-p1-t0]."
        )
        citations = parse_citations(text)
        assert len(citations) == 3

    def test_parse_no_citations(self) -> None:
        """Handle text with no citations."""
        text = "This is an answer without any citations."
        citations = parse_citations(text)
        assert len(citations) == 0

    def test_parse_insufficient_evidence(self) -> None:
        """Handle insufficient_evidence response."""
        text = "insufficient_evidence"
        citations = parse_citations(text)
        assert len(citations) == 0


class TestCitationValidation:
    """Test citation validation against retrieved evidence."""

    def test_valid_citations(self) -> None:
        """Valid citations should pass validation."""
        citations = [
            Citation(paper_id="P01", page=1, evidence_id="ev-P01-p1-t0"),
            Citation(paper_id="P01", page=2, evidence_id="ev-P01-p2-tab0"),
        ]
        retrieved_ids = {"ev-P01-p1-t0", "ev-P01-p2-tab0", "ev-P01-p1-cap0"}

        valid, warnings = validate_citations(citations, retrieved_ids)
        assert len(valid) == 2
        assert len(warnings) == 0

    def test_invalid_citation_detected(self) -> None:
        """Citations referencing unretrieved evidence should be flagged."""
        citations = [
            Citation(paper_id="P01", page=1, evidence_id="ev-P01-p1-t0"),
            Citation(paper_id="P01", page=5, evidence_id="ev-FAKE-id"),
        ]
        retrieved_ids = {"ev-P01-p1-t0"}

        valid, warnings = validate_citations(citations, retrieved_ids)
        assert len(valid) == 1
        assert len(warnings) == 1
        assert "ev-FAKE-id" in warnings[0]

    def test_all_citations_invalid(self) -> None:
        """All invalid citations should generate warnings."""
        citations = [
            Citation(paper_id="P01", page=99, evidence_id="fake-1"),
            Citation(paper_id="P02", page=99, evidence_id="fake-2"),
        ]
        retrieved_ids = {"ev-P01-p1-t0"}

        valid, warnings = validate_citations(citations, retrieved_ids)
        assert len(valid) == 0
        assert len(warnings) == 2


class TestCitationMetrics:
    """Test citation metric calculations."""

    def _make_answer(
        self,
        text: str = "Test answer",
        citations: list[Citation] | None = None,
        retrieved: list[str] | None = None,
        abstained: bool = False,
    ) -> Answer:
        return Answer(
            answer=text,
            abstained=abstained,
            citations=citations or [],
            retrieved=retrieved or [],
            retrieved_evidence=[
                RetrievalResult(
                    evidence=Evidence(
                        evidence_id=i,
                        paper_id="P01",
                        page=1,
                        modality=Modality.TEXT,
                        text="test",
                        extraction_method=ExtractionMethod.PYMUPDF_TEXT,
                    ),
                    score=0.9,
                    rank=n + 1,
                )
                for n, i in enumerate(retrieved or [])
            ],
            mode=AnswerMode.TEXT_RAG,
            model_id="test",
        )

    def test_citation_precision_all_valid(self) -> None:
        """All citations valid → precision = 1.0."""
        answer = self._make_answer(
            citations=[
                Citation(paper_id="P01", page=1, evidence_id="ev-1"),
            ],
            retrieved=["ev-1"],
        )
        assert citation_precision(answer) == 1.0

    def test_citation_precision_half_valid(self) -> None:
        """Half citations valid → precision = 0.5."""
        answer = self._make_answer(
            citations=[
                Citation(paper_id="P01", page=1, evidence_id="ev-1"),
                Citation(paper_id="P01", page=2, evidence_id="ev-fake"),
            ],
            retrieved=["ev-1"],
        )
        assert citation_precision(answer) == 0.5

    def test_citation_precision_no_citations(self) -> None:
        """No citations → undefined, never a perfect score."""
        answer = self._make_answer(citations=[])
        assert citation_precision(answer) is None

    def test_evidence_recall_all_found(self) -> None:
        """All gold evidence found → recall = 1.0."""
        results = [
            RetrievalResult(
                evidence=Evidence(
                    evidence_id="ev-1",
                    paper_id="P01",
                    page=1,
                    modality=Modality.TEXT,
                    text="test",
                    extraction_method=ExtractionMethod.PYMUPDF_TEXT,
                ),
                score=0.9,
                rank=1,
            ),
        ]
        gold = [
            GoldEvidence(paper_id="P01", page=1, evidence_id="ev-1", modality=Modality.TEXT),
        ]
        assert evidence_recall_at_k(results, gold) == 1.0

    def test_evidence_recall_none_found(self) -> None:
        """No gold evidence found → recall = 0.0."""
        results = [
            RetrievalResult(
                evidence=Evidence(
                    evidence_id="ev-other",
                    paper_id="P01",
                    page=5,
                    modality=Modality.TEXT,
                    text="test",
                    extraction_method=ExtractionMethod.PYMUPDF_TEXT,
                ),
                score=0.5,
                rank=1,
            ),
        ]
        gold = [
            GoldEvidence(paper_id="P01", page=1, evidence_id="ev-1", modality=Modality.TEXT),
        ]
        assert evidence_recall_at_k(results, gold) == 0.0

    def test_evidence_recall_page_fallback(self) -> None:
        """Fall back to page-level matching when no evidence_id in gold."""
        results = [
            RetrievalResult(
                evidence=Evidence(
                    evidence_id="ev-different-id",
                    paper_id="P01",
                    page=1,
                    modality=Modality.TEXT,
                    text="test",
                    extraction_method=ExtractionMethod.PYMUPDF_TEXT,
                ),
                score=0.8,
                rank=1,
            ),
        ]
        gold = [
            GoldEvidence(paper_id="P01", page=1, modality=Modality.TEXT),
        ]
        assert evidence_recall_at_k(results, gold) == 1.0


class TestAbstentionQuality:
    """Test abstention quality evaluation."""

    def _make_question(self, answerable: bool = True) -> BenchmarkQuestion:
        return BenchmarkQuestion(
            question_id="Q-test",
            question="Test question?",
            source_papers=["P01"],
            gold_answer="Test answer" if answerable else "insufficient_evidence",
            gold_evidence=[],
            modality=Modality.TEXT,
            difficulty=Difficulty.EASY,
            answerable=answerable,
        )

    def _make_answer(self, abstained: bool = False) -> Answer:
        return Answer(
            answer="insufficient_evidence" if abstained else "Some answer",
            abstained=abstained,
            mode=AnswerMode.TEXT_RAG,
            model_id="test",
        )

    def test_correct_abstention(self) -> None:
        """Abstaining on unanswerable question is correct."""
        quality = abstention_quality(
            self._make_answer(abstained=True),
            self._make_question(answerable=False),
        )
        assert quality["correct_abstention"] is True

    def test_incorrect_abstention(self) -> None:
        """Abstaining on answerable question is incorrect."""
        quality = abstention_quality(
            self._make_answer(abstained=True),
            self._make_question(answerable=True),
        )
        assert quality["incorrect_abstention"] is True

    def test_missed_abstention(self) -> None:
        """Answering unanswerable question should have been abstention."""
        quality = abstention_quality(
            self._make_answer(abstained=False),
            self._make_question(answerable=False),
        )
        assert quality["missed_abstention"] is True

    def test_correct_answer(self) -> None:
        """Answering answerable question is correct."""
        quality = abstention_quality(
            self._make_answer(abstained=False),
            self._make_question(answerable=True),
        )
        assert quality["answered_answerable"] is True


class TestValidateAnswerCitations:
    """Test citation validation against evidence store."""

    def test_validates_against_store(self, sample_evidence: list[Evidence]) -> None:
        """Citations should be validated against the evidence store."""
        evidence_lookup = {ev.evidence_id: ev for ev in sample_evidence}

        answer = Answer(
            answer="Test [P01, p.1, ev-P01-p1-t0] and [P01, p.99, ev-FAKE]",
            citations=[
                Citation(paper_id="P01", page=1, evidence_id="ev-P01-p1-t0"),
                Citation(paper_id="P01", page=99, evidence_id="ev-FAKE"),
            ],
            mode=AnswerMode.TEXT_RAG,
            model_id="test",
        )

        records = validate_answer_citations(answer, evidence_lookup)
        assert len(records) == 2
        assert records[0]["found_in_store"] is True
        assert records[0]["paper_id_match"] is True
        assert records[0]["page_match"] is True
        assert records[1]["found_in_store"] is False

    def test_detects_wrong_page(self, sample_evidence: list[Evidence]) -> None:
        """Detect when citation page doesn't match evidence page."""
        evidence_lookup = {ev.evidence_id: ev for ev in sample_evidence}

        answer = Answer(
            answer="Test [P01, p.99, ev-P01-p1-t0]",
            citations=[
                Citation(paper_id="P01", page=99, evidence_id="ev-P01-p1-t0"),
            ],
            mode=AnswerMode.TEXT_RAG,
            model_id="test",
        )

        records = validate_answer_citations(answer, evidence_lookup)
        assert records[0]["found_in_store"] is True
        assert records[0]["page_match"] is False
