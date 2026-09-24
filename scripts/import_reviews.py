"""Convert completed blinded review records to evaluator judgments."""

import argparse
import json
from pathlib import Path


def import_reviews(reviews: Path, key: Path, out: Path):
    mapping = json.loads(key.read_text())
    judgments, seen = [], set()
    for line in reviews.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rid = row["review_id"]
        if rid not in mapping or rid in seen:
            raise ValueError("Unknown or duplicate review ID")
        seen.add(rid)
        if row.get("correctness") is None:
            continue
        if row["correctness"] not in (0, 1) or not row.get("annotator") or not row.get("rationale"):
            raise ValueError("Scored reviews require correctness 0/1, annotator and rationale")
        judgments.append(
            {
                **mapping[rid],
                **{
                    k: row.get(k)
                    for k in ("correctness", "semantic_citation_support", "annotator", "rationale")
                },
            }
        )
    if not judgments:
        raise ValueError("No completed reviews; fill review_template.jsonl first")
    if out.exists():
        raise ValueError("Output exists; choose a new path to preserve prior judgments")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(j) for j in judgments) + "\n")
    return len(judgments)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("reviews", "key", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(f"Imported {import_reviews(args.reviews, args.key, args.out)} judgments")
