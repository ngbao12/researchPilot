"""
Embedding providers for ResearchPilot.

Supports local sentence-transformers (CPU-friendly) and OpenAI embeddings.
Includes a deterministic mock for offline tests.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract embedding interface."""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts, returning (N, dim) float32 array."""
        ...

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query, returning (dim,) float32 array."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimension."""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model identifier for reproducibility logging."""
        ...


class SentenceTransformerEmbedder(EmbeddingProvider):
    """Local CPU-friendly embeddings via sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        logger.info("Loading sentence-transformer model: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_sentence_embedding_dimension()
        logger.info("Model loaded. Dimension: %d", self._dim)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts in batches."""
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        embeddings = self._model.encode(
            texts,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embeddings.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query."""
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return f"sentence-transformers/{self._model_name}"


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI API-based embeddings."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        batch_size: int = 100,
    ) -> None:
        from openai import OpenAI

        self._model = model
        self._batch_size = batch_size
        self._client = OpenAI(api_key=api_key)
        self._dim = 1536 if "3-small" in model else 3072
        self._total_tokens = 0
        logger.info("OpenAI embedder initialized: model=%s, dim=%d", model, self._dim)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts via OpenAI API in batches."""
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        all_embeddings = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            response = self._client.embeddings.create(model=self._model, input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            self._total_tokens += response.usage.total_tokens
            logger.debug(
                "Embedded batch %d-%d, tokens used: %d",
                i,
                i + len(batch),
                response.usage.total_tokens,
            )

        return np.array(all_embeddings, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query."""
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return f"openai/{self._model}"

    @property
    def total_tokens(self) -> int:
        """Total tokens used across all API calls."""
        return self._total_tokens


class MockEmbedder(EmbeddingProvider):
    """
    Deterministic mock embedder for offline tests.
    Produces consistent embeddings based on text hash.
    """

    def __init__(self, dimension: int = 384) -> None:
        self._dim = dimension
        logger.info("MockEmbedder initialized with dimension %d", dimension)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Generate deterministic embeddings from text hashes."""
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        embeddings = []
        for text in texts:
            text_hash = hashlib.sha256(text.encode()).digest()
            rng = np.random.RandomState(int.from_bytes(text_hash[:4], "big"))
            vec = rng.randn(self._dim).astype(np.float32)
            vec /= np.linalg.norm(vec) + 1e-10
            embeddings.append(vec)

        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query deterministically."""
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return "mock/deterministic"


class LexicalEmbedder(EmbeddingProvider):
    """Offline signed token hashing baseline; lexical, not a semantic model."""

    def __init__(self, dimension: int = 4096):
        self._dim = dimension

    def embed(self, texts: list[str]) -> np.ndarray:
        import re

        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        stop = {
            "the",
            "a",
            "an",
            "of",
            "on",
            "in",
            "and",
            "or",
            "to",
            "is",
            "are",
            "what",
            "how",
            "does",
            "do",
            "for",
            "with",
            "by",
            "as",
            "it",
            "that",
            "this",
            "from",
        }
        for i, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                if word in stop or len(word) < 2:
                    continue
                digest = hashlib.sha256(word.encode()).digest()
                vectors[i, int.from_bytes(digest[:4], "big") % self.dimension] += (
                    1 if digest[4] % 2 else -1
                )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-10)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return "lexical-hash-v1"


def create_embedder(
    provider: str = "local",
    model: str = "all-MiniLM-L6-v2",
    **kwargs: Any,
) -> EmbeddingProvider:
    """Factory function to create an embedding provider."""
    dimension = kwargs.pop("dimension", None)
    if provider == "lexical":
        if model != "lexical-hash-v1":
            raise ValueError("Lexical provider requires lexical-hash-v1")
        return LexicalEmbedder(dimension=dimension or 4096)
    if provider == "local":
        return SentenceTransformerEmbedder(model_name=model)
    elif provider == "openai":
        return OpenAIEmbedder(model=model, **kwargs)
    elif provider == "mock":
        return MockEmbedder(dimension=dimension or 384, **kwargs)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
