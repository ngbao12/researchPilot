"""Run controlled baselines; use --ablations for k/caption comparisons."""

from pathlib import Path
import argparse
from researchpilot.cli import load_config
from researchpilot.pipeline import benchmark
from researchpilot.schema import AnswerMode

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--questions", type=Path, default=Path("data/questions.jsonl"))
    parser.add_argument("--index-dir", type=Path, default=Path("artifacts/current/index"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--modes", default="closed-book,text-rag,table-rag")
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--split", choices=["all", "dev", "held-out"], default="all")
    parser.add_argument("--ablations", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    modes = [AnswerMode(m.strip()) for m in args.modes.split(",")]
    if args.ablations:
        for k in (3, 5, 10):
            benchmark(
                args.questions, args.out / f"k{k}", config, args.index_dir, modes, k, args.split
            )
        benchmark(
            args.questions,
            args.out / "no-captions",
            config,
            args.index_dir,
            [AnswerMode.TEXT_RAG, AnswerMode.TABLE_RAG],
            5,
            args.split,
            True,
        )
    else:
        benchmark(args.questions, args.out, config, args.index_dir, modes, args.top_k, args.split)
