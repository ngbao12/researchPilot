"""
ResearchPilot Indexing — chunk, deduplicate, embed, and build FAISS index.

Chunks by document structure, preserves page/section metadata,
deduplicates near-identical chunks, and builds a local FAISS index.
Stores immutable corpus manifest and index config alongside the index.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np

from researchpilot.providers.embedding import EmbeddingProvider, create_embedder
from researchpilot.schema import (
    CorpusData,
    Evidence,
    IndexConfig,
    Modality,
)

logger = logging.getLogger(__name__)


# ── Chunking ───────────────────────────────────────────────────────────────────


def chunk_evidence(
    evidence_list: list[Evidence],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    min_chunk_size: int = 50,
) -> list[Evidence]:
    """
    Chunk evidence items by token-approximate character count.

    Long text blocks are split into overlapping chunks while preserving
    page and section metadata. Tables and captions are kept as single chunks.

    Args:
        evidence_list: Raw evidence items from extraction.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.
        min_chunk_size: Minimum chunk size to keep.

    Returns:
        List of chunked evidence items with updated chunk_index.
    """
    if not 0 <= chunk_overlap < chunk_size and 0 < min_chunk_size <= chunk_size:
        raise ValueError("Require overlap < chunk_size and min_chunk_size <= chunk_size")
    chunked: list[Evidence] = []
    chunk_idx = 0

    for ev in evidence_list:
        chunk_idx = 0
        text = ev.text.strip()

        # Tables and captions: keep as single chunks
        if ev.modality in (Modality.TABLE, Modality.CAPTION, Modality.FIGURE):
            if len(text) >= min_chunk_size or ev.modality == Modality.TABLE:
                new_ev = ev.model_copy(
                    update={
                        "evidence_id": f"{ev.evidence_id}-c{chunk_idx}",
                        "chunk_index": chunk_idx,
                    }
                )
                chunked.append(new_ev)
                chunk_idx += 1
            continue

        # Text: split into overlapping chunks
        if len(text) <= chunk_size:
            if len(text) >= min_chunk_size:
                new_ev = ev.model_copy(
                    update={
                        "evidence_id": f"{ev.evidence_id}-c{chunk_idx}",
                        "chunk_index": chunk_idx,
                    }
                )
                chunked.append(new_ev)
                chunk_idx += 1
            continue

        # Split long text
        start = 0
        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start + min_chunk_size, end)
                last_newline = text.rfind("\n", start + min_chunk_size, end)
                break_point = max(last_period, last_newline)
                if break_point > start + max(min_chunk_size, chunk_overlap):
                    end = break_point + 1

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= min_chunk_size:
                new_ev = ev.model_copy(
                    update={
                        "evidence_id": f"{ev.evidence_id}-c{chunk_idx}",
                        "text": chunk_text,
                        "chunk_index": chunk_idx,
                    }
                )
                chunked.append(new_ev)
                chunk_idx += 1

            start = max(start + 1, end - chunk_overlap) if end < len(text) else end

    logger.info(
        "Chunked %d evidence items into %d chunks",
        len(evidence_list),
        len(chunked),
    )
    return chunked


# ── Deduplication ──────────────────────────────────────────────────────────────


def deduplicate_chunks(
    chunks: list[Evidence],
    embedder: EmbeddingProvider,
    threshold: float = 0.95,
) -> list[Evidence]:
    """
    Remove near-duplicate chunks using embedding cosine similarity.

    Args:
        chunks: Chunked evidence items.
        embedder: Embedding provider.
        threshold: Cosine similarity threshold for deduplication.

    Returns:
        Deduplicated list of evidence items.
    """
    if not chunks or len(chunks) <= 1:
        return chunks

    texts = [c.text for c in chunks]
    embeddings = embedder.embed(texts)

    # Compute pairwise similarities
    keep_mask = [True] * len(chunks)
    for i in range(len(chunks)):
        if not keep_mask[i]:
            continue
        for j in range(i + 1, len(chunks)):
            if not keep_mask[j]:
                continue
            if (chunks[i].paper_id, chunks[i].page, chunks[i].modality) != (
                chunks[j].paper_id,
                chunks[j].page,
                chunks[j].modality,
            ):
                continue
            sim = float(np.dot(embeddings[i], embeddings[j]))
            if sim >= threshold:
                keep_mask[j] = False

    deduped = [c for c, keep in zip(chunks, keep_mask) if keep]
    removed = len(chunks) - len(deduped)
    if removed > 0:
        logger.info("Deduplication removed %d/%d chunks", removed, len(chunks))

    return deduped


# ── FAISS Index ────────────────────────────────────────────────────────────────


class EvidenceIndex:
    """FAISS-based evidence index with metadata mapping."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        config: IndexConfig,
    ) -> None:
        import faiss

        self.embedder = embedder
        self.config = config
        self._evidence_map: dict[int, Evidence] = {}
        self._id_to_faiss_idx: dict[str, int] = {}
        self._index: faiss.Index | None = None

    def build(self, evidence: list[Evidence]) -> None:
        """Build FAISS index from evidence items."""
        import faiss

        if not evidence:
            raise ValueError("No evidence to index")

        start = time.perf_counter()

        # Get texts for embedding
        texts = []
        for ev in evidence:
            if ev.modality == Modality.FIGURE and not ev.text:
                # For figures without captions, use a placeholder
                texts.append(f"[Figure from {ev.paper_id} page {ev.page}]")
            else:
                texts.append(ev.text)

        # Embed
        logger.info("Embedding %d evidence chunks...", len(texts))
        embeddings = self.embedder.embed(texts)

        # Build index
        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)  # Inner product (cosine sim with normalized vectors)
        faiss.normalize_L2(embeddings)
        self._index.add(embeddings)
        self._evidence_map.clear()
        self._id_to_faiss_idx.clear()

        # Build metadata maps
        for idx, ev in enumerate(evidence):
            self._evidence_map[idx] = ev
            self._id_to_faiss_idx[ev.evidence_id] = idx

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Built FAISS index: %d vectors, dim=%d, %.0fms",
            len(evidence),
            dim,
            elapsed_ms,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        modality_filter: set[Modality] | None = None,
        paper_filter: set[str] | None = None,
    ) -> list[tuple[Evidence, float]]:
        """
        Search for relevant evidence.

        Args:
            query: Search query string.
            top_k: Number of results to return.
            modality_filter: Only return these modalities (optional).
            paper_filter: Only return from these paper_ids (optional).

        Returns:
            List of (evidence, score) tuples, sorted by relevance.
        """
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if self._index is None or self._index.ntotal == 0:
            return []

        query_vec = self.embedder.embed_query(query).reshape(1, -1)

        # Search more than top_k to allow filtering
        import faiss

        faiss.normalize_L2(query_vec)
        search_k = (
            self._index.ntotal
            if (modality_filter is not None or paper_filter is not None)
            else min(top_k, self._index.ntotal)
        )
        scores, indices = self._index.search(query_vec, search_k)

        results: list[tuple[Evidence, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            ev = self._evidence_map.get(int(idx))
            if ev is None:
                continue
            if modality_filter is not None and ev.modality not in modality_filter:
                continue
            if paper_filter is not None and ev.paper_id not in paper_filter:
                continue
            results.append((ev, float(score)))
            if len(results) >= top_k:
                break

        return results

    def get_evidence_by_id(self, evidence_id: str) -> Evidence | None:
        """Look up evidence by ID."""
        idx = self._id_to_faiss_idx.get(evidence_id)
        if idx is not None:
            return self._evidence_map.get(idx)
        return None

    def save(self, output_dir: Path) -> None:
        """Save index and metadata to disk."""
        import faiss

        output_dir = Path(output_dir)
        if (output_dir / "index.faiss").exists():
            raise ValueError("Index exists; choose a new directory to preserve the snapshot")
        output_dir.mkdir(parents=True, exist_ok=True)

        if self._index is not None:
            faiss.write_index(self._index, str(output_dir / "index.faiss"))

        # Save evidence map
        evidence_data = {
            str(idx): ev.model_dump(mode="json") for idx, ev in self._evidence_map.items()
        }
        with open(output_dir / "evidence_map.json", "w") as f:
            json.dump(evidence_data, f, indent=2, default=str)

        # Save config
        with open(output_dir / "index_config.json", "w") as f:
            f.write(self.config.model_dump_json(indent=2))

        import hashlib

        checksums = {
            name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
            for name in ("index.faiss", "evidence_map.json", "index_config.json")
        }
        (output_dir / "checksums.json").write_text(json.dumps(checksums, indent=2))
        logger.info("Index saved to %s", output_dir)

    def load(self, index_dir: Path) -> None:
        """Load index and metadata from disk."""
        import faiss

        index_dir = Path(index_dir)
        index_path = index_dir / "index.faiss"
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found: {index_path}")

        import hashlib

        if (index_dir / "checksums.json").exists():
            for name, digest in json.loads((index_dir / "checksums.json").read_text()).items():
                if name not in {"index.faiss", "evidence_map.json", "index_config.json"}:
                    raise ValueError("Unexpected index checksum entry")
                if hashlib.sha256((index_dir / name).read_bytes()).hexdigest() != digest:
                    raise ValueError(f"Index checksum mismatch: {name}")
        saved_config = IndexConfig.model_validate_json(
            (index_dir / "index_config.json").read_text()
        )
        if (
            saved_config.embedding_provider,
            saved_config.embedding_model,
            saved_config.embedding_dim,
        ) != (
            self.config.embedding_provider,
            self.config.embedding_model,
            self.config.embedding_dim,
        ):
            raise ValueError("Embedding configuration differs from saved index; rebuild the index")
        self.config = saved_config
        self._index = faiss.read_index(str(index_path))
        if self._index.d != self.embedder.dimension:
            raise ValueError("Embedding dimension differs from saved index")

        # Load evidence map
        evidence_path = index_dir / "evidence_map.json"
        with open(evidence_path) as f:
            evidence_data = json.load(f)

        self._evidence_map = {}
        self._id_to_faiss_idx = {}
        for idx_str, ev_dict in evidence_data.items():
            idx = int(idx_str)
            ev = Evidence(**ev_dict)
            self._evidence_map[idx] = ev
            self._id_to_faiss_idx[ev.evidence_id] = idx

        logger.info(
            "Loaded index from %s: %d vectors",
            index_dir,
            self._index.ntotal,
        )

    @property
    def size(self) -> int:
        """Number of indexed evidence items."""
        return self._index.ntotal if self._index else 0


def build_index(
    corpus: CorpusData,
    config: IndexConfig,
    output_dir: Path,
    embedder: EmbeddingProvider | None = None,
) -> EvidenceIndex:
    """
    Build a complete evidence index from corpus data.

    Steps:
    1. Chunk evidence by document structure
    2. Deduplicate near-identical chunks
    3. Embed and build FAISS index
    4. Save to disk

    Args:
        corpus: Extracted corpus data.
        config: Index configuration.
        output_dir: Directory to save index artifacts.
        embedder: Optional pre-created embedding provider.

    Returns:
        Built EvidenceIndex.
    """
    if embedder is None:
        embedder = create_embedder(
            provider=config.embedding_provider,
            model=config.embedding_model,
            dimension=config.embedding_dim,
        )

    # 1. Chunk
    chunks = chunk_evidence(
        corpus.all_evidence,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        min_chunk_size=config.min_chunk_size,
    )

    # 2. Deduplicate
    chunks = deduplicate_chunks(chunks, embedder, threshold=config.dedup_threshold)

    # 3. Build index
    index = EvidenceIndex(embedder, config)
    index.build(chunks)

    # 4. Save
    output_dir = Path(output_dir)
    index.save(output_dir)

    # Save corpus manifest alongside index
    manifest_file = output_dir / "corpus_manifest.json"
    with open(manifest_file, "w") as f:
        f.write(corpus.manifest.model_dump_json(indent=2))

    import hashlib

    (output_dir / "corpus.sha256").write_text(
        hashlib.sha256(corpus.model_dump_json().encode()).hexdigest()
    )
    return index
