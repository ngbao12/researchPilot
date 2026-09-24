"""Comparison with shared generation guard and per-paper evidence."""

from __future__ import annotations

import time

from researchpilot.generate import generate_answer
from researchpilot.retrieve import retrieve_for_comparison
from researchpilot.schema import AnswerMode, ComparisonResult


def compare_papers(
    question,
    paper_a_id,
    paper_b_id,
    index,
    llm,
    mode=AnswerMode.TABLE_RAG,
    top_k=5,
    vlm=None,
    temperature=0.0,
    max_tokens=512,
    seed=None,
    abstention_threshold=0.15,
):
    if paper_a_id == paper_b_id:
        raise ValueError("Choose two different papers")
    start = time.perf_counter()
    a, b = retrieve_for_comparison(question, index, paper_a_id, paper_b_id, mode, top_k, vlm)
    flags = []
    for paper, results in [(paper_a_id, a), (paper_b_id, b)]:
        if not results or max(r.score for r in results) < abstention_threshold:
            flags.append(f"Insufficient evidence for {paper}")
    answer = generate_answer(
        question,
        [] if flags else a + b,
        llm,
        mode,
        temperature=temperature,
        max_tokens=max_tokens,
        seed=seed,
        abstention_threshold=abstention_threshold,
    )
    if not answer.abstained and {c.paper_id for c in answer.citations} != {paper_a_id, paper_b_id}:
        flags.append("Both papers must be cited to support a comparison")
        answer.answer, answer.abstained, answer.citations = "insufficient_evidence", True, []
    answer.retrieved = [r.evidence.evidence_id for r in a + b]
    answer.retrieved_evidence = a + b
    answer.warnings.extend(flags)
    answer.latency_ms = (time.perf_counter() - start) * 1000
    return ComparisonResult(
        question=question,
        paper_a_id=paper_a_id,
        paper_b_id=paper_b_id,
        paper_a_evidence=a,
        paper_b_evidence=b,
        answer=answer,
        unsupported_flags=flags,
    )
