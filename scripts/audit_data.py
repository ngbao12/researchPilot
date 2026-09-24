"""Validate source provenance and prepare deterministic human extraction review."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from researchpilot.evaluation import load_questions
from researchpilot.schema import CorpusData


def audit(corpus_path, questions_path, out):
    corpus = CorpusData.model_validate_json(corpus_path.read_text())
    questions = load_questions(questions_path)
    by_paper = {e.paper_id: e for e in corpus.extractions}
    issues = []
    for q in questions:
        for p in q.source_papers:
            if p not in by_paper:
                issues.append(f"{q.question_id}: unknown paper {p}")
        for gold in q.gold_evidence:
            ext = by_paper.get(gold.paper_id)
            if not ext or not 1 <= gold.page <= ext.page_count:
                issues.append(f"{q.question_id}: invalid page {gold.paper_id}/{gold.page}")
            if gold.evidence_id and not any(
                e.evidence_id == gold.evidence_id for e in corpus.all_evidence
            ):
                issues.append(f"{q.question_id}: missing evidence {gold.evidence_id}")
    samples = []
    # Stratify by paper and modality; at least 20% of each stratum.
    rng = random.Random(42)
    for paper in sorted(by_paper):
        for mod in ("text", "table", "caption", "figure"):
            evidence = sorted(
                [e for e in corpus.all_evidence if e.paper_id == paper and e.modality.value == mod],
                key=lambda e: e.evidence_id,
            )
            samples.extend(rng.sample(evidence, math.ceil(len(evidence) * 0.2)))
    out.mkdir(parents=True, exist_ok=True)
    review = out / "extraction_review.jsonl"
    if not review.exists():
        review.write_text(
            "\n".join(
                json.dumps(
                    {
                        "evidence": e.model_dump(mode="json"),
                        "reviewer": "",
                        "matches_source": None,
                        "notes": "",
                    }
                )
                for e in samples
            )
            + "\n"
        )
    report = {
        "paper_count": len(corpus.manifest.papers),
        "question_count": len(questions),
        "evidence_count": len(corpus.all_evidence),
        "review_sample_count": len(samples),
        "review_status": "pending human review",
        "held_out": sum(q.held_out for q in questions),
        "human_verified_questions": sum(
            q.verification_status == "human_verified" for q in questions
        ),
        "issues": issues,
        "source_hashes": {
            p.paper_id: hashlib.sha256(Path(p.local_path).read_bytes()).hexdigest()
            for p in corpus.manifest.papers
            if Path(p.local_path).is_file()
        },
        "research_readiness": "Requires 10-20 license-verified papers, 30-50 human-authored/verified questions, untouched held-out set and completed human scoring",
    }
    (out / "data_audit.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return bool(issues)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("artifacts/current/corpus/corpus.json"))
    parser.add_argument("--questions", type=Path, default=Path("data/questions.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("reports/data-audit"))
    args = parser.parse_args()
    raise SystemExit(audit(args.corpus, args.questions, args.out))
