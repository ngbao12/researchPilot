"""Compatibility wrapper; same evaluation implementation as the CLI."""

from pathlib import Path
import argparse
from researchpilot.evaluation import evaluate_runs

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--judgments", type=Path)
    args = parser.parse_args()
    evaluate_runs(
        args.run, args.questions or args.run / "questions.jsonl", args.report, args.judgments
    )
    print(f"Report saved to {args.report or args.run / 'report.md'}")
