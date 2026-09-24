"""Shared query and benchmark orchestration for CLI and scripts."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from importlib.metadata import version

from researchpilot.evaluation import load_questions
from researchpilot.generate import generate_answer
from researchpilot.index import EvidenceIndex
from researchpilot.providers.embedding import create_embedder
from researchpilot.providers.llm import create_llm
from researchpilot.retrieve import retrieve_evidence
from researchpilot.schema import AnswerMode, BenchmarkPrediction, BenchmarkRun, IndexConfig


def load_index(path: Path, config: dict | None = None) -> EvidenceIndex:
    cfg = IndexConfig.model_validate_json((path / "index_config.json").read_text())
    # Saved embedding config is authoritative; do not query with a different model.
    if config and config.get("index"):
        requested = IndexConfig(**config["index"])
        if (requested.embedding_provider, requested.embedding_model, requested.embedding_dim) != (
            cfg.embedding_provider,
            cfg.embedding_model,
            cfg.embedding_dim,
        ):
            raise ValueError(
                "Configured embedder differs from index. Rebuild with this config or use the matching config."
            )
    embedder = create_embedder(
        provider=cfg.embedding_provider, model=cfg.embedding_model, dimension=cfg.embedding_dim
    )
    index = EvidenceIndex(embedder, cfg)
    index.load(path)
    return index


def generator(config):
    g = config.get("generate", {})
    return create_llm(
        provider=g.get("llm_provider", "extractive"), model=g.get("llm_model", "quotes-v1")
    )


def ask_question(
    question, mode, index, llm, config, top_k=None, papers=None, without_captions=False
):
    if mode == AnswerMode.VLM_RAG:
        raise ValueError("VLM is not evaluated: use caption-rag; no images are sent to a model")
    start = time.perf_counter()
    ret, gen = config.get("retrieve", {}), config.get("generate", {})
    k = top_k if top_k is not None else ret.get("top_k", 5)
    if k < 1:
        raise ValueError("top_k must be positive")
    results = []
    if mode != AnswerMode.CLOSED_BOOK:
        if index is None:
            raise ValueError("Index is required for retrieval")
        results = retrieve_evidence(
            question,
            index,
            mode,
            top_k=k,
            paper_filter=papers,
            score_threshold=ret.get("score_threshold", 0.0),
            without_captions=without_captions,
        )
    retrieval_ms = (time.perf_counter() - start) * 1000
    answer = generate_answer(
        question,
        results,
        llm,
        mode,
        temperature=gen.get("temperature", 0.0),
        max_tokens=gen.get("max_tokens", 512),
        seed=gen.get("seed", 42),
        abstention_threshold=gen.get("abstention_threshold", 0.15),
    )
    answer.retrieval_latency_ms = retrieval_ms
    answer.latency_ms = (time.perf_counter() - start) * 1000
    return answer


def benchmark(
    questions_path: Path,
    out: Path,
    config: dict,
    index_path: Path,
    modes: list[AnswerMode],
    top_k=None,
    split="all",
    without_captions=False,
):
    if AnswerMode.VLM_RAG in modes:
        raise ValueError("VLM is not evaluated; no caption fallback under the VLM label")
    all_questions = load_questions(questions_path)
    questions = [q for q in all_questions if split == "all" or q.held_out == (split == "held-out")]
    if not questions:
        raise ValueError(f"No questions in split {split}")
    index = (
        load_index(index_path, config) if any(m != AnswerMode.CLOSED_BOOK for m in modes) else None
    )
    llm = generator(config)
    out.mkdir(parents=True, exist_ok=True)
    if any((out / f"{m.value}.json").exists() for m in modes):
        raise ValueError(
            "Run already exists; use a new output directory to preserve the audit trail"
        )
    metadata = {
        "settings": config,
        "top_k": top_k if top_k is not None else config.get("retrieve", {}).get("top_k", 5),
        "split": split,
        "without_captions": without_captions,
        "questions_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        "question_ids": [q.question_id for q in questions],
        "index_config": index.config.model_dump() if index else None,
        "index_sha256": hashlib.sha256((index_path / "index.faiss").read_bytes()).hexdigest()
        if index
        else None,
        "corpus_sha256": (index_path / "corpus.sha256").read_text()
        if index and (index_path / "corpus.sha256").exists()
        else None,
        "hardware": platform.platform(),
        "processor": platform.processor(),
        "python": sys.version,
        "packages": {p: version(p) for p in ["numpy", "pydantic", "faiss-cpu", "pymupdf"]},
        "input_representation": "text/table/captions; no image inference",
        "generation_kind": "offline demonstration"
        if llm.model_id.startswith(("mock/", "extractive/"))
        else "LLM",
    }
    (out / "config.json").write_text(json.dumps(metadata, indent=2))
    (out / "questions.jsonl").write_bytes(questions_path.read_bytes())
    for mode in modes:
        run = BenchmarkRun(mode=mode, model_id=llm.model_id, config=metadata)
        for q in questions:
            answer = ask_question(
                q.question,
                mode,
                index,
                llm,
                config,
                top_k=top_k,
                papers=set(q.source_papers) if q.source_papers else None,
                without_captions=without_captions,
            )
            run.predictions.append(BenchmarkPrediction(question_id=q.question_id, answer=answer))
        run.completed_at = datetime.utcnow()
        (out / f"{mode.value}.json").write_text(run.model_dump_json(indent=2))
    return len(questions) * len(modes)
