# Data provenance and review status

The repository includes metadata and 12 legacy draft questions over four local PDFs. Human authorship, annotator identities and manual verification were not documented; all questions remain `verification_status: unverified`. AI-assisted corrections on 2026-09-24 do not change this status. There is no genuinely untouched held-out subset.

## Source licenses

The license links on each arXiv abstract page were checked on 2026-09-24:

| Paper | Source | License shown |
|---|---|---|
| P01 MobileNets | https://arxiv.org/abs/1704.04861 | arXiv non-exclusive distribution license |
| P02 EfficientNet | https://arxiv.org/abs/1905.11946 | arXiv non-exclusive distribution license |
| P03 ViT | https://arxiv.org/abs/2010.11929 | arXiv non-exclusive distribution license |
| P04 EfficientViT | https://arxiv.org/abs/2205.14756 | CC BY 4.0 |

License URLs and check dates are stored in `papers_manifest.json`. The previous assertion that every paper was CC BY 4.0 was incorrect. The current corpus therefore does not fulfill the research brief's permissively licensed corpus requirement. PDFs and derived full-text artifacts are excluded from source control.

Each local PDF has a SHA-256 fingerprint in the manifest. A mismatched download fails validation rather than silently changing page references. Source URLs may resolve to revised versions; obtain the version matching the fingerprint or create a new reviewed manifest and re-annotate questions. Do not silently update hashes to hide a version mismatch.

## Corrections

- Q01: factorization description is on PDF page 2.
- Q03: EfficientNet Table 2 is on PDF page 6; both B7 and GPipe report 84.3% at the displayed precision. Table 4 on the same page provides inference latency.
- Q07: the 8–9x computation reduction is described on MobileNets page 3; the old reference to a cost table on page 4 was misleading.
- Q08: EfficientViT Table 2 labels Nano, Orin and A100; the old V100 answer was unsupported.
- Q09: ViT Figure 3 is on page 7, with the sequence-length explanation on page 5.
- Q12: ViT's 86M parameters are on page 5 and ImageNet-only 77.91% result on page 15; EfficientNet-B7 results are on page 6.

Other annotations, especially unanswerability and inferred figure interpretations, require independent review. Do not treat the absence of an extracted keyword as proof that a question is unanswerable.

## Review workflow

Run `python scripts/audit_data.py` after building the corpus. It checks IDs/pages and generates a deterministic sample of at least 20% of each paper/modality stratum in `reports/data-audit/extraction_review.jsonl`. Review each item against the original PDF or crop and fill `reviewer`, `matches_source` and `notes`. Sampling is automatic; actual review is not.

For the research-scale corpus, add papers with verified permissive licenses and explicit version URLs, then write 30–50 questions independently of system output, balancing text, tables, figures, comparisons and deliberately unanswerable cases. Reserve a fresh held-out subset before development and record annotator IDs and decisions. `--split held-out` fails when the subset is empty.
