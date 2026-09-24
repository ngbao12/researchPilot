"""
ResearchPilot Retrieval — top-k evidence retrieval with scoring and filtering.

Supports text-only, table-aware, and caption-based retrieval modes.
Figure path: index captions, then optionally give the actual crop to a VLM.
"""

from __future__ import annotations

import logging
import time

from researchpilot.index import EvidenceIndex
from researchpilot.providers.vlm import VLMProvider
from researchpilot.schema import (
    AnswerMode,
    Modality,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


# ── Modality Filters by Mode ──────────────────────────────────────────────────

MODE_MODALITY_FILTERS = {
    AnswerMode.CLOSED_BOOK: set(),  # No retrieval
    AnswerMode.TEXT_RAG: {Modality.TEXT, Modality.CAPTION},
    AnswerMode.TABLE_RAG: {Modality.TEXT, Modality.TABLE, Modality.CAPTION},
    AnswerMode.CAPTION_RAG: {Modality.TEXT, Modality.CAPTION},
    AnswerMode.VLM_RAG: {Modality.TEXT, Modality.TABLE, Modality.CAPTION, Modality.FIGURE},
}


def retrieve_evidence(
    query: str,
    index: EvidenceIndex,
    mode: AnswerMode,
    top_k: int = 5,
    score_threshold: float = 0.0,
    paper_filter: set[str] | None = None,
    vlm: VLMProvider | None = None,
    without_captions: bool = False,
) -> list[RetrievalResult]:
    """
    Retrieve top-k evidence for a query.

    Args:
        query: Search query.
        index: Evidence index.
        mode: Retrieval mode (determines modality filtering).
        top_k: Number of results.
        score_threshold: Minimum similarity score.
        paper_filter: Only return from these paper_ids (optional).
        vlm: VLM provider for figure processing (optional).

    Returns:
        List of RetrievalResult sorted by relevance.
    """
    if mode == AnswerMode.CLOSED_BOOK:
        logger.info("Closed-book mode: no retrieval performed")
        return []

    if mode == AnswerMode.VLM_RAG:
        raise ValueError("VLM evaluation is not implemented; use caption-rag (no image reasoning)")
    start = time.perf_counter()

    # Get modality filter for this mode
    modality_filter = set(MODE_MODALITY_FILTERS[mode])
    if without_captions:
        modality_filter.discard(Modality.CAPTION)

    # Search index
    raw_results = index.search(
        query=query,
        top_k=top_k,
        modality_filter=modality_filter,
        paper_filter=paper_filter,
    )

    # Build results with filtering
    results: list[RetrievalResult] = []
    for rank, (evidence, score) in enumerate(raw_results):
        if score < score_threshold:
            continue

        # For VLM mode: enhance figure evidence with VLM description
        if (
            mode == AnswerMode.VLM_RAG
            and evidence.modality == Modality.FIGURE
            and evidence.crop_path
            and vlm is not None
        ):
            try:
                vlm_response = vlm.describe_figure(
                    image_path=evidence.crop_path,
                    caption=evidence.text,
                    question=query,
                )
                # Augment evidence text with VLM description
                evidence = evidence.model_copy(
                    update={
                        "text": (
                            f"{evidence.text}\n\n"
                            f"[VLM Description ({vlm.model_id})]: {vlm_response.text}"
                        ),
                    }
                )
                if not vlm.is_true_vlm:
                    logger.debug(
                        "Caption-only fallback used for figure %s",
                        evidence.evidence_id,
                    )
            except Exception as e:
                logger.warning(
                    "VLM processing failed for %s: %s",
                    evidence.evidence_id,
                    e,
                )

        results.append(
            RetrievalResult(
                evidence=evidence,
                score=score,
                rank=rank + 1,
            )
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "Retrieved %d results for mode=%s in %.0fms (top score: %.4f)",
        len(results),
        mode.value,
        elapsed_ms,
        results[0].score if results else 0.0,
    )

    return results


def retrieve_for_comparison(
    query: str,
    index: EvidenceIndex,
    paper_a_id: str,
    paper_b_id: str,
    mode: AnswerMode = AnswerMode.TABLE_RAG,
    top_k: int = 5,
    vlm: VLMProvider | None = None,
) -> tuple[list[RetrievalResult], list[RetrievalResult]]:
    """
    Retrieve evidence for two papers separately for comparison.

    Returns:
        Tuple of (paper_a_results, paper_b_results).
    """
    results_a = retrieve_evidence(
        query=query,
        index=index,
        mode=mode,
        top_k=top_k,
        paper_filter={paper_a_id},
        vlm=vlm,
    )

    results_b = retrieve_evidence(
        query=query,
        index=index,
        mode=mode,
        top_k=top_k,
        paper_filter={paper_b_id},
        vlm=vlm,
    )

    return results_a, results_b
