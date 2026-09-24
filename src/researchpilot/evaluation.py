"""Re-runnable evaluation. Structural metrics are not semantic correctness."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from researchpilot.generate import claim_sentences, parse_citations
from researchpilot.schema import BenchmarkQuestion, BenchmarkRun


def load_questions(path: Path) -> list[BenchmarkQuestion]:
    questions = [
        BenchmarkQuestion.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if not questions or len({q.question_id for q in questions}) != len(questions):
        raise ValueError("Questions must be nonempty and have unique IDs")
    return questions


def ratio(n: int, d: int) -> dict:
    return {"numerator": n, "denominator": d, "value": n / d if d else None}


def score_prediction(pred, q):
    answer = pred.answer
    evidence = {r.evidence.evidence_id: r.evidence for r in answer.retrieved_evidence}
    # Audit the original generation, including citations rejected by the guard.
    citations = re.findall(
        r"\[([^,\]]+),\s*p\.(\d+),\s*([^\]]+)\]", answer.raw_response or answer.answer
    )
    valid = sum(
        eid.strip() in evidence
        and evidence[eid.strip()].paper_id == paper.strip()
        and evidence[eid.strip()].page == int(page)
        for paper, page, eid in citations
    )
    claims = [] if answer.abstained else claim_sentences(answer.answer)
    covered = sum(bool(parse_citations(c)) for c in claims)
    hits = 0
    for gold in q.gold_evidence:
        hits += any(
            (
                ev.evidence_id == gold.evidence_id
                or ev.evidence_id.startswith(gold.evidence_id + "-c")
            )
            if gold.evidence_id
            else (ev.paper_id == gold.paper_id and ev.page == gold.page)
            for ev in evidence.values()
        )
    return {
        "question_id": q.question_id,
        "category": q.category,
        "modality": q.modality.value,
        "held_out": q.held_out,
        "verification_status": q.verification_status,
        "citation_valid": int(valid),
        "citation_total": len(citations),
        "claims_covered": covered,
        "claims_total": len(claims),
        "evidence_hits": hits,
        "evidence_total": len(q.gold_evidence),
        "answerable": q.answerable,
        "abstained": answer.abstained,
        "latency_ms": answer.latency_ms,
        "correctness": None,
        "semantic_citation_support": None,
    }


def aggregate(rows):
    return {
        "n": len(rows),
        "structural_citation_precision": ratio(
            sum(r["citation_valid"] for r in rows), sum(r["citation_total"] for r in rows)
        ),
        "citation_coverage": ratio(
            sum(r["claims_covered"] for r in rows), sum(r["claims_total"] for r in rows)
        ),
        "evidence_recall": ratio(
            sum(r["evidence_hits"] for r in rows), sum(r["evidence_total"] for r in rows)
        ),
        "abstention_precision": ratio(
            sum(r["abstained"] and not r["answerable"] for r in rows),
            sum(r["abstained"] for r in rows),
        ),
        "abstention_recall": ratio(
            sum(r["abstained"] and not r["answerable"] for r in rows),
            sum(not r["answerable"] for r in rows),
        ),
        "incorrect_abstentions": sum(r["abstained"] and r["answerable"] for r in rows),
        "missed_abstentions": sum(not r["abstained"] and not r["answerable"] for r in rows),
        "answer_correctness": ratio(
            sum(r["correctness"] or 0 for r in rows),
            sum(r["correctness"] is not None for r in rows),
        ),
        "semantic_citation_support": ratio(
            sum(r["semantic_citation_support"] or 0 for r in rows),
            sum(r["semantic_citation_support"] is not None for r in rows),
        ),
        "latency_p50_ms": float(np.percentile([r["latency_ms"] for r in rows], 50))
        if rows
        else None,
        "latency_p95_ms": float(np.percentile([r["latency_ms"] for r in rows], 95))
        if rows
        else None,
    }


def evaluate_runs(
    run_dir: Path,
    questions_path: Path,
    report_path: Path | None = None,
    judgments_path: Path | None = None,
):
    questions = {q.question_id: q for q in load_questions(questions_path)}
    question_hash = hashlib.sha256(questions_path.read_bytes()).hexdigest()
    judgments = {}
    if judgments_path:
        for line in judgments_path.read_text().splitlines():
            if not line.strip():
                continue
            j = json.loads(line)
            key = (j["run_id"], j["question_id"])
            if (
                key in judgments
                or j.get("correctness") not in (0, 1)
                or not j.get("annotator")
                or not j.get("rationale")
            ):
                raise ValueError(
                    "Judgments require unique run/question, correctness 0/1, annotator and rationale"
                )
            if j.get("semantic_citation_support") not in (None, 0, 1):
                raise ValueError("semantic_citation_support must be 0, 1 or null")
            judgments[key] = j
    if not run_dir.is_dir():
        raise ValueError(f"Run directory not found: {run_dir}")
    runs = []
    for path in sorted(run_dir.glob("*.json")):
        if path.name in {
            "config.json",
            "evaluation_metrics.json",
            "blind_key.json",
            "data_audit.json",
        }:
            continue
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict) or not {"run_id", "mode", "predictions"} <= raw.keys():
            continue
        run = BenchmarkRun.model_validate(raw)
        if run.config.get("questions_sha256") and run.config["questions_sha256"] != question_hash:
            raise ValueError("Questions differ from the benchmark snapshot")
        if not run.predictions or len({p.question_id for p in run.predictions}) != len(
            run.predictions
        ):
            raise ValueError("Empty run or duplicate predictions")
        runs.append(run)
    if not runs:
        raise ValueError("No benchmark predictions found")
    metrics, review, blind_key, failures = [], [], {}, []
    for run in runs:
        rows = []
        for pred in run.predictions:
            if pred.question_id not in questions:
                raise ValueError(f"Unknown question: {pred.question_id}")
            q = questions[pred.question_id]
            row = score_prediction(pred, q)
            judgment = judgments.get((run.run_id, q.question_id))
            if judgment:
                row.update(
                    correctness=judgment["correctness"],
                    semantic_citation_support=judgment.get("semantic_citation_support"),
                    judgment=judgment,
                )
            rows.append(row)
            review_id = hashlib.sha256(f"{run.run_id}/{q.question_id}".encode()).hexdigest()[:16]
            blind_key[review_id] = {"run_id": run.run_id, "question_id": q.question_id}
            review.append(
                {
                    "review_id": review_id,
                    "question": q.question,
                    "gold_answer": q.gold_answer,
                    "gold_evidence": [g.model_dump(mode="json") for g in q.gold_evidence],
                    "answer": pred.answer.answer,
                    "evidence": [
                        r.evidence.model_dump(mode="json") for r in pred.answer.retrieved_evidence
                    ],
                    "correctness": None,
                    "semantic_citation_support": None,
                    "annotator": "",
                    "rationale": "",
                }
            )
            if (
                row["citation_valid"] < row["citation_total"]
                or row["abstained"] == row["answerable"]
                or row["evidence_hits"] < row["evidence_total"]
            ):
                failures.append(
                    {
                        "mode": run.mode.value,
                        "question_id": q.question_id,
                        "question": q.question,
                        "answer": pred.answer.answer,
                        "warnings": pred.answer.warnings,
                        "gold_evidence": [g.model_dump(mode="json") for g in q.gold_evidence],
                        "retrieved_evidence": [
                            r.model_dump(mode="json") for r in pred.answer.retrieved_evidence
                        ],
                    }
                )
        m = {
            "run_id": run.run_id,
            "mode": run.mode.value,
            "model_id": run.model_id,
            "config": run.config,
            **aggregate(rows),
            "per_question": rows,
        }
        for field in ("category", "modality", "held_out"):
            m["per_" + field] = {
                str(v): aggregate([r for r in rows if r[field] == v])
                for v in sorted({r[field] for r in rows}, key=str)
            }
        m["tokens"] = sum(p.answer.usage.get("total_tokens", 0) for p in run.predictions)
        m["usage_kinds"] = sorted({p.answer.usage_kind for p in run.predictions})
        m["api_cost_usd"] = None  # No invented pricing; attach audited billing externally.
        metrics.append(m)
    (run_dir / "evaluation_metrics.json").write_text(json.dumps(metrics, indent=2))
    # Do not overwrite a human's completed review file.
    review_path = run_dir / "review_template.jsonl"
    if not review_path.exists():
        review.sort(key=lambda r: r["review_id"])
        review_path.write_text("\n".join(json.dumps(r) for r in review) + "\n")
    (run_dir / "blind_key.json").write_text(json.dumps(blind_key, indent=2))
    (run_dir / "failure_cases.jsonl").write_text(
        "\n".join(json.dumps(r) for r in failures[:5]) + "\n"
    )
    report = [
        "# ResearchPilot — measured execution report",
        "",
        "Structural citation validity and coverage do **not** measure factual correctness or semantic support. Undefined ratios are N/A. Gold annotations remain unverified unless independently audited. VLM: **not evaluated**.",
        "",
        "| Mode | Model | N | Citation validity | Recall | Correctness scored |",
        "|---|---|---:|---|---|---|",
    ]

    def fmt(r):
        return f"{r['numerator']}/{r['denominator']}" if r["denominator"] else "N/A (0 denominator)"

    for m in metrics:
        report.append(
            f"| {m['mode']} | {m['model_id']} | {m['n']} | {fmt(m['structural_citation_precision'])} | {fmt(m['evidence_recall'])} | {fmt(m['answer_correctness'])} |"
        )
    report += [
        "",
        "Full numerator/denominator, per-category, per-modality, held-out results, latency p50/p95, usage, configs and per-question decisions are in `evaluation_metrics.json`. Latency includes retrieval and generation, excludes initial model/index loading. Offline token counts are estimates; API cost is not measured.",
        "",
        "## Failure cases (up to five observed cases)",
    ]
    for f in failures[:5]:
        refs = ", ".join(f"{g['paper_id']} p.{g['page']}" for g in f["gold_evidence"])
        ids = ", ".join(r["evidence"]["evidence_id"] for r in f["retrieved_evidence"])
        report += [
            "",
            f"### {f['mode']} / {f['question_id']}",
            f["question"],
            f"- Answer: {f['answer']}",
            f"- Expected source references (unverified gold): {refs or 'unanswerable'}",
            f"- Retrieved: {ids or 'none'}",
            f"- Warnings: {'; '.join(f['warnings']) or 'none'}",
            "- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.",
        ]
    report += [
        "",
        "## Human review",
        "Score review_template.jsonl blind to mode; keep blind_key.json separate from reviewers. Map review_id back to run_id/question_id, save JSONL judgments, then pass --judgments. Use correctness=1 only when all required facts match and no contradicted facts are added. Record annotator and rationale. Semantic support requires checking each cited claim against the source.",
    ]
    output = report_path or run_dir / "report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(report) + "\n")
    return metrics
