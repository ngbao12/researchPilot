# ResearchPilot — measured execution report

Structural citation validity and coverage do **not** measure factual correctness or semantic support. Undefined ratios are N/A. Gold annotations remain unverified unless independently audited. VLM: **not evaluated**.

| Mode | Model | N | Citation validity | Recall | Correctness scored |
|---|---|---:|---|---|---|
| closed-book | extractive/quotes-v1 | 12 | N/A (0 denominator) | 0/18 | N/A (0 denominator) |
| table-rag | extractive/quotes-v1 | 12 | 14/14 | 13/18 | N/A (0 denominator) |
| text-rag | extractive/quotes-v1 | 12 | 14/14 | 13/18 | N/A (0 denominator) |

Full numerator/denominator, per-category, per-modality, held-out results, latency p50/p95, usage, configs and per-question decisions are in `evaluation_metrics.json`. Latency includes retrieval and generation, excludes initial model/index loading. Offline token counts are estimates; API cost is not measured.

## Failure cases (up to five observed cases)

### closed-book / Q01
What is the key architectural innovation in MobileNets that reduces computational cost?
- Answer: insufficient_evidence
- Expected source references (unverified gold): P01 p.1, P01 p.2
- Retrieved: none
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### closed-book / Q02
What is the compound scaling method proposed in EfficientNet, and how does it differ from single-dimension scaling?
- Answer: insufficient_evidence
- Expected source references (unverified gold): P02 p.1, P02 p.3
- Retrieved: none
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### closed-book / Q03
What ImageNet top-1 accuracy does EfficientNet-B7 achieve, and how does it compare to the previous best?
- Answer: insufficient_evidence
- Expected source references (unverified gold): P02 p.6, P02 p.6
- Retrieved: none
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### closed-book / Q04
How does the Vision Transformer (ViT) handle variable-resolution images during inference?
- Answer: insufficient_evidence
- Expected source references (unverified gold): P03 p.4
- Retrieved: none
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

### closed-book / Q05
Compare the scaling approaches of MobileNets and EfficientNet for achieving different accuracy-efficiency tradeoffs.
- Answer: insufficient_evidence
- Expected source references (unverified gold): P01 p.4, P02 p.3
- Retrieved: none
- Warnings: none
- Diagnosis: inspect the saved source excerpts in failure_cases.jsonl. A retrieval miss, rejected citation, or abstention mismatch triggered this entry; this is not a human correctness judgment.

## Human review
Score review_template.jsonl blind to mode; keep blind_key.json separate from reviewers. Map review_id back to run_id/question_id, save JSONL judgments, then pass --judgments. Use correctness=1 only when all required facts match and no contradicted facts are added. Record annotator and rationale. Semantic support requires checking each cited claim against the source.
