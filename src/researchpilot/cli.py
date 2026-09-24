"""CLI for a reproducible offline or API-backed paper analysis pipeline."""

from __future__ import annotations

import json
import logging
from functools import wraps
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from researchpilot.schema import AnswerMode, CorpusData, CorpusManifest, IndexConfig


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def setup_logging(level="INFO"):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)


def load_config(config_path="configs/default.yaml"):
    path = Path(config_path)
    if not path.is_file():
        raise click.ClickException(f"Config not found: {path}")
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        raise click.ClickException("Config must be a YAML mapping")
    return config


def errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, OSError, ImportError) as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapped


@click.group()
@click.option("--config", default="configs/default.yaml", show_default=True)
@click.option("--log-level", default="WARNING")
@click.pass_context
def main(ctx, config, log_level):
    """ResearchPilot: cited PDF evidence, honest reproducible evaluation."""
    load_dotenv()
    setup_logging(log_level)
    ctx.obj = load_config(config)


@main.command()
@click.option("--manifest", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--out", default="artifacts/current/corpus", type=click.Path(path_type=Path))
@click.pass_obj
@errors
def ingest(config, manifest, out):
    """Extract local PDFs and preserve errors, pages and source evidence."""
    from researchpilot.ingest import ingest_corpus

    cfg = config.get("ingest", {})
    corpus = ingest_corpus(
        CorpusManifest.model_validate_json(manifest.read_text()),
        out,
        extract_tables_flag=cfg.get("extract_tables", True),
        extract_figures_flag=cfg.get("extract_figures", True),
        extract_captions_flag=cfg.get("extract_captions", True),
        max_pages=cfg.get("max_pages", 200),
        max_file_size_mb=cfg.get("max_file_size_mb", 50),
    )
    click.echo(f"Saved {len(corpus.all_evidence)} evidence items to {out}")
    for e in corpus.extractions:
        click.echo(
            f"{e.paper_id}: pages={e.page_count}, text={e.text_blocks}, tables={e.tables}, figures={e.figures}, errors={len(e.errors)}"
        )
    if any(not e.evidence for e in corpus.extractions):
        raise click.ClickException(
            "At least one paper failed extraction; inspect corpus.json errors"
        )


@main.command()
@click.option("--corpus", default="artifacts/current/corpus", type=click.Path(path_type=Path))
@click.option("--config", "index_config", default=None, type=click.Path(path_type=Path))
@click.option("--out", default="artifacts/current/index", type=click.Path(path_type=Path))
@click.pass_obj
@errors
def index(config, corpus, index_config, out):
    """Build an index with immutable corpus/config snapshots."""
    from researchpilot.index import build_index

    if index_config:
        config = load_config(index_config)
    cfg = IndexConfig(**config.get("index", {}))
    result = build_index(
        CorpusData.model_validate_json((corpus / "corpus.json").read_text()), cfg, out
    )
    click.echo(f"Indexed {result.size} evidence chunks at {out}")


@main.command()
@click.option("--question", required=True)
@click.option("--mode", type=click.Choice([m.value for m in AnswerMode]), default="text-rag")
@click.option("--index-dir", default="artifacts/current/index", type=click.Path(path_type=Path))
@click.option("--top-k", type=click.IntRange(min=1), default=None)
@click.option("--paper-id", multiple=True)
@click.option("--json", "--json-output", "json_flag", is_flag=True)
@click.pass_obj
@errors
def ask(config, question, mode, index_dir, top_k, paper_id, json_flag):
    """Answer or abstain, retaining raw output and retrieved evidence."""
    from researchpilot.pipeline import ask_question, generator, load_index

    mode = AnswerMode(mode)
    index = load_index(index_dir, config) if mode != AnswerMode.CLOSED_BOOK else None
    answer = ask_question(
        question, mode, index, generator(config), config, top_k, set(paper_id) or None
    )
    if json_flag:
        click.echo(answer.model_dump_json(indent=2))
    else:
        click.echo(answer.answer)
        click.echo(f"Model: {answer.model_id} | {answer.latency_ms:.1f} ms")
        for warning in answer.warnings:
            click.echo(f"Warning: {warning}")


@main.command()
@click.option("--paper-a", required=True)
@click.option("--paper-b", required=True)
@click.option("--question", required=True)
@click.option("--index-dir", default="artifacts/current/index", type=click.Path(path_type=Path))
@click.option("--top-k", type=click.IntRange(min=1), default=None)
@click.option("--json", "--json-output", "json_flag", is_flag=True)
@click.pass_obj
@errors
def compare(config, paper_a, paper_b, question, index_dir, top_k, json_flag):
    """Compare sources, showing a per-paper evidence table."""
    from researchpilot.compare import compare_papers
    from researchpilot.pipeline import generator, load_index

    gen = config.get("generate", {})
    result = compare_papers(
        question,
        paper_a,
        paper_b,
        load_index(index_dir, config),
        generator(config),
        top_k=top_k or config.get("retrieve", {}).get("top_k", 5),
        temperature=gen.get("temperature", 0),
        max_tokens=gen.get("max_tokens", 512),
        seed=gen.get("seed", 42),
        abstention_threshold=gen.get("abstention_threshold", 0.15),
    )
    if json_flag:
        click.echo(result.model_dump_json(indent=2))
    else:
        click.echo(result.answer.answer)
        click.echo("Paper | Page | Score | Evidence | Excerpt")
        for r in result.paper_a_evidence + result.paper_b_evidence:
            e = r.evidence
            click.echo(
                f"{e.paper_id} | {e.page} | {r.score:.3f} | {e.evidence_id} | {e.text[:140].replace(chr(10), ' ')}"
            )
        for flag in result.unsupported_flags:
            click.echo(f"UNSUPPORTED: {flag}")


@main.command()
@click.option("--questions", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--modes", default="closed-book,text-rag,table-rag")
@click.option("--index-dir", default="artifacts/current/index", type=click.Path(path_type=Path))
@click.option("--out", required=True, type=click.Path(path_type=Path))
@click.option("--top-k", type=click.IntRange(min=1), default=None)
@click.option("--split", type=click.Choice(["all", "dev", "held-out"]), default="all")
@click.option("--without-captions", is_flag=True)
@click.pass_obj
@errors
def benchmark(config, questions, modes, index_dir, out, top_k, split, without_captions):
    """Run identical questions/settings across baselines; never overwrite a run."""
    from researchpilot.pipeline import benchmark as run

    count = run(
        questions,
        out,
        config,
        index_dir,
        [AnswerMode(m.strip()) for m in modes.split(",")],
        top_k,
        split,
        without_captions,
    )
    click.echo(f"Saved {count} predictions to {out}")


@main.command()
@click.option("--run", "run_dir", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--questions", default=None, type=click.Path(path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=None)
@click.option("--judgments", type=click.Path(path_type=Path), default=None)
@click.pass_obj
@errors
def evaluate(config, run_dir, questions, out, judgments):
    """Write metrics/report; semantic correctness requires human judgments."""
    from researchpilot.evaluation import evaluate_runs

    questions = questions or (run_dir / "questions.jsonl")
    metrics = evaluate_runs(run_dir, questions, out, judgments)
    click.echo(f"Evaluated {len(metrics)} runs; report saved to {out or run_dir / 'report.md'}")


@main.command()
@click.option("--index-dir", default="artifacts/current/index", type=click.Path(path_type=Path))
@click.option("--corpus-dir", default="artifacts/current/corpus", type=click.Path(path_type=Path))
@click.option("--evidence-id", default=None)
@click.option("--paper-id", default=None)
@click.option("--query", default=None)
@click.option("--top-k", type=click.IntRange(min=1), default=5)
@click.pass_obj
@errors
def inspect(config, index_dir, corpus_dir, evidence_id, paper_id, query, top_k):
    """Inspect extraction health, source excerpts and retrieval scores."""
    from researchpilot.pipeline import load_index

    corpus = CorpusData.model_validate_json((corpus_dir / "corpus.json").read_text())
    for ext in corpus.extractions:
        click.echo(json.dumps(ext.model_dump(mode="json", exclude={"evidence"})))
    index = load_index(index_dir, config) if query or evidence_id else None
    if evidence_id:
        evidence = index.get_evidence_by_id(evidence_id) or next(
            (e for e in corpus.all_evidence if e.evidence_id == evidence_id), None
        )
        if evidence is None:
            raise click.ClickException(f"Evidence not found: {evidence_id}")
        click.echo(evidence.model_dump_json(indent=2))
    if paper_id:
        for e in [e for e in corpus.all_evidence if e.paper_id == paper_id][:20]:
            click.echo(e.model_dump_json())
    if query:
        for e, score in index.search(
            query, top_k=top_k, paper_filter={paper_id} if paper_id else None
        ):
            click.echo(json.dumps({"score": score, "evidence": e.model_dump(mode="json")}))


if __name__ == "__main__":
    main()
