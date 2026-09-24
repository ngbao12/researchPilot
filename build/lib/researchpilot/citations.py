"""
ResearchPilot Citations — citation parsing, validation, and metrics.

Ensures every answer citation maps to a stored evidence ID, paper ID,
page number, modality, and excerpt or crop.
"""

from __future__ import annotations

import logging
from typing import Any

from researchpilot.schema import (
    Answer,
    BenchmarkQuestion,
    Evidence,
    GoldEvidence,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


def citation_precision(answer: Answer) -> float | None:
    """Structural precision of RAW citations; undefined when no citations exist."""
    from researchpilot.generate import parse_citations

    citations = parse_citations(answer.raw_response or answer.answer) or answer.citations
    if not citations:
        return None
    lookup = {r.evidence.evidence_id: r.evidence for r in answer.retrieved_evidence}
    valid = sum(
        c.evidence_id in lookup
        and lookup[c.evidence_id].paper_id == c.paper_id
        and lookup[c.evidence_id].page == c.page
        for c in citations
    )
    return valid / len(citations)


def citation_support_rate(answer: Answer, results: list[RetrievalResult]) -> float | None:
    """Citation coverage proxy only; semantic entailment requires manual review."""
    from researchpilot.generate import claim_sentences, parse_citations

    if answer.abstained:
        return None
    claims = claim_sentences(answer.answer)
    return sum(bool(parse_citations(c)) for c in claims) / len(claims) if claims else None


def evidence_recall_at_k(
    retrieved: list[RetrievalResult],
    gold_evidence: list[GoldEvidence],
) -> float:
    """
    Compute evidence recall@k: fraction of gold evidence IDs
    that appear in the retrieved set.

    If gold evidence has no IDs, falls back to page-level matching.

    Returns:
        Float in [0, 1], or 1.0 if no gold evidence.
    """
    if not gold_evidence:
        return 1.0

    retrieved_ids = {r.evidence.evidence_id for r in retrieved}
    retrieved_pages = {(r.evidence.paper_id, r.evidence.page) for r in retrieved}

    hits = 0
    for gold in gold_evidence:
        if gold.evidence_id and gold.evidence_id in retrieved_ids:
            hits += 1
        elif not gold.evidence_id and (gold.paper_id, gold.page) in retrieved_pages:
            hits += 1

    return hits / len(gold_evidence)


def abstention_quality(
    answer: Answer,
    question: BenchmarkQuestion,
) -> dict[str, bool]:
    """
    Evaluate abstention quality for a single question.

    Returns dict with:
        - correct_abstention: True if abstained on unanswerable question
        - incorrect_abstention: True if abstained on answerable question
        - missed_abstention: True if answered unanswerable question
        - answered_answerable: True if answered answerable question
    """
    return {
        "correct_abstention": answer.abstained and not question.answerable,
        "incorrect_abstention": answer.abstained and question.answerable,
        "missed_abstention": not answer.abstained and not question.answerable,
        "answered_answerable": not answer.abstained and question.answerable,
    }


def validate_answer_citations(
    answer: Answer,
    evidence_lookup: dict[str, Evidence],
) -> list[dict[str, Any]]:
    """
    Validate each citation in an answer against the evidence store.

    Returns a list of validation records with details per citation.
    """
    records = []
    for cit in answer.citations:
        ev = evidence_lookup.get(cit.evidence_id)
        record = {
            "citation": f"[{cit.paper_id}, p.{cit.page}, {cit.evidence_id}]",
            "found_in_store": ev is not None,
            "paper_id_match": ev.paper_id == cit.paper_id if ev else False,
            "page_match": ev.page == cit.page if ev else False,
            "modality": ev.modality.value if ev else None,
            "excerpt": ev.text[:200] if ev else None,
        }
        records.append(record)

        if ev is None:
            logger.warning("Citation references unknown evidence: %s", cit.evidence_id)
        elif ev.paper_id != cit.paper_id:
            logger.warning(
                "Citation paper_id mismatch: cited %s, evidence has %s",
                cit.paper_id,
                ev.paper_id,
            )
        elif ev.page != cit.page:
            logger.warning(
                "Citation page mismatch: cited p.%d, evidence has p.%d",
                cit.page,
                ev.page,
            )

    return records


def compute_citation_metrics(
    answers: list[Answer],
    questions: list[BenchmarkQuestion],
    results_per_question: list[list[RetrievalResult]],
) -> dict[str, float]:
    """
    Compute aggregate citation metrics across a benchmark run.

    Returns dict with:
        - avg_citation_precision
        - avg_citation_support_rate
        - avg_evidence_recall
        - abstention_precision (correct abstentions / total abstentions)
        - abstention_recall (correct abstentions / unanswerable questions)
    """
    precisions = []
    support_rates = []
    recalls = []
    abstention_stats = {
        "correct_abstention": 0,
        "incorrect_abstention": 0,
        "missed_abstention": 0,
        "answered_answerable": 0,
    }

    for answer, question, results in zip(answers, questions, results_per_question):
        precision = citation_precision(answer)
        if precision is not None:
            precisions.append(precision)
        coverage = citation_support_rate(answer, results)
        if coverage is not None:
            support_rates.append(coverage)
        recalls.append(evidence_recall_at_k(results, question.gold_evidence))

        quality = abstention_quality(answer, question)
        for key, val in quality.items():
            if val:
                abstention_stats[key] += 1

    total_abstentions = (
        abstention_stats["correct_abstention"] + abstention_stats["incorrect_abstention"]
    )
    total_unanswerable = (
        abstention_stats["correct_abstention"] + abstention_stats["missed_abstention"]
    )

    return {
        "avg_citation_precision": (sum(precisions) / len(precisions) if precisions else None),
        "avg_citation_support_rate": (
            sum(support_rates) / len(support_rates) if support_rates else None
        ),
        "avg_evidence_recall": (sum(recalls) / len(recalls) if recalls else 0.0),
        "abstention_precision": (
            abstention_stats["correct_abstention"] / total_abstentions
            if total_abstentions > 0
            else 1.0
        ),
        "abstention_recall": (
            abstention_stats["correct_abstention"] / total_unanswerable
            if total_unanswerable > 0
            else 1.0
        ),
    }
