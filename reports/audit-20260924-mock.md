> Historical output from the pre-fix evaluator. These metrics are known to be misleading and must not be cited. See experiment_report.md for the corrected evaluation.

# ResearchPilot — Experiment Report

Generated: 2026-09-24T02:15:10.485865Z

Questions: 12

## Mode: closed-book
- Model: `mock/deterministic`
- Questions: 12
- Answered: 0 | Abstained: 12
- Citation Precision: 1.000
- Citation Support Rate: 1.000
- Latency p50: 0ms | p95: 0ms
- Total tokens: 742

### Abstention Quality
- Correct abstentions: 2
- Incorrect abstentions: 10
- Missed abstentions: 0
- Correct answers: 0

### Per-Modality Results
- figure: 0.00 answer rate (2 questions)
- table: 0.00 answer rate (4 questions)
- text: 0.00 answer rate (6 questions)

### Per-Category Results
- ablation: 0.00 answer rate (1 questions)
- architecture: 0.00 answer rate (3 questions)
- comparison: 0.00 answer rate (2 questions)
- methodology: 0.00 answer rate (2 questions)
- results: 0.00 answer rate (2 questions)
- unanswerable: 0.00 answer rate (2 questions)

## Mode: table-rag
- Model: `mock/deterministic`
- Questions: 12
- Answered: 11 | Abstained: 1
- Citation Precision: 1.000
- Citation Support Rate: 0.083
- Latency p50: 0ms | p95: 0ms
- Total tokens: 3087

### Abstention Quality
- Correct abstentions: 0
- Incorrect abstentions: 1
- Missed abstentions: 2
- Correct answers: 9

### Per-Modality Results
- figure: 1.00 answer rate (2 questions)
- table: 0.75 answer rate (4 questions)
- text: 1.00 answer rate (6 questions)

### Per-Category Results
- ablation: 1.00 answer rate (1 questions)
- architecture: 1.00 answer rate (3 questions)
- comparison: 1.00 answer rate (2 questions)
- methodology: 1.00 answer rate (2 questions)
- results: 0.50 answer rate (2 questions)
- unanswerable: 1.00 answer rate (2 questions)

## Mode: text-rag
- Model: `mock/deterministic`
- Questions: 12
- Answered: 11 | Abstained: 1
- Citation Precision: 1.000
- Citation Support Rate: 0.083
- Latency p50: 0ms | p95: 0ms
- Total tokens: 2269

### Abstention Quality
- Correct abstentions: 0
- Incorrect abstentions: 1
- Missed abstentions: 2
- Correct answers: 9

### Per-Modality Results
- figure: 1.00 answer rate (2 questions)
- table: 0.75 answer rate (4 questions)
- text: 1.00 answer rate (6 questions)

### Per-Category Results
- ablation: 1.00 answer rate (1 questions)
- architecture: 1.00 answer rate (3 questions)
- comparison: 1.00 answer rate (2 questions)
- methodology: 1.00 answer rate (2 questions)
- results: 0.50 answer rate (2 questions)
- unanswerable: 1.00 answer rate (2 questions)

## Summary Table

| Mode | Questions | Answered | Abstained | Cit. Precision | Cit. Support | p50 (ms) | p95 (ms) | Tokens |
|------|-----------|----------|-----------|----------------|--------------|----------|----------|--------|
| closed-book | 12 | 0 | 12 | 1.000 | 1.000 | 0 | 0 | 742 |
| table-rag | 12 | 11 | 1 | 1.000 | 0.083 | 0 | 0 | 3087 |
| text-rag | 12 | 11 | 1 | 1.000 | 0.083 | 0 | 0 | 2269 |

## Limitations

- Sample sizes are small (N=12)
- Answer correctness requires manual rubric scoring (not automated)
- Evidence recall requires gold evidence IDs (partially available)
- VLM path: **not evaluated** (caption-only fallback used)
