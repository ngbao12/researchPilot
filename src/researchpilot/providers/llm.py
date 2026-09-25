"""
LLM providers for ResearchPilot.

Supports OpenAI API and a deterministic mock for offline tests.
Records model ID, version, prompt, temperature, hardware, and token usage.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
API_ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


class ProviderResponseError(RuntimeError):
    """An upstream response cannot be used as an answer."""


@dataclass
class LLMResponse:
    """Structured LLM response with metadata."""

    text: str
    model_id: str
    model_version: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    temperature: float = 0.0
    seed: int | None = None
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract LLM interface."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        seed: int | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model identifier for reproducibility."""
        ...


class OpenAIGenerator(LLMProvider):
    """OpenAI API-based LLM generation."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        provider: str = "openai",
        language: str | None = None,
    ) -> None:
        from openai import OpenAI

        self._model = model
        if provider not in API_ENDPOINTS:
            raise ValueError("Unsupported API provider")
        self._provider = provider
        self._language = language
        self._client = OpenAI(
            api_key=api_key,
            timeout=60,
            max_retries=0,
            base_url=API_ENDPOINTS[provider],
        )
        self._total_tokens = 0
        logger.info("OpenAI generator initialized: model=%s", model)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        seed: int | None = None,
    ) -> LLMResponse:
        """Generate via OpenAI API."""
        if self._language and not getattr(self, "_json_mode", False):
            system_prompt += (
                "\nWrite the answer in "
                + ("English" if self._language == "en" else "Vietnamese")
                + ". Preserve literal source quotations and citation identifiers."
            )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._provider == "groq" and self._model.startswith("openai/gpt-oss-"):
            kwargs["reasoning_effort"] = getattr(self, "reasoning_effort", "low")
            kwargs["extra_body"] = {"include_reasoning": False}
        if self._provider == "gemini":
            kwargs["reasoning_effort"] = "low"
        if getattr(self, "_json_mode", False):
            kwargs["response_format"] = {"type": "json_object"}
        if seed is not None and self._provider != "gemini":
            kwargs["seed"] = seed

        response = self._client.chat.completions.create(**kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if not response.choices:
            raise ProviderResponseError("empty_choices")
        choice = response.choices[0]
        if not choice.message or not isinstance(choice.message.content, str) or not choice.message.content.strip():
            raise ProviderResponseError("empty_content")
        usage = response.usage
        def token_count(name):
            value = getattr(usage, name, 0) if usage else 0
            return value if isinstance(value, int) and value >= 0 else 0


        self._total_tokens += token_count("total_tokens")

        logger.info(
            "LLM response: model=%s, tokens=%d, latency=%.0fms",
            self._model,
            token_count("total_tokens"),
            elapsed_ms,
        )

        return LLMResponse(
            text=choice.message.content or "",
            model_id=f"{self._provider}/{self._model}",
            model_version=response.model or self._model,
            prompt_tokens=token_count("prompt_tokens"),
            completion_tokens=token_count("completion_tokens"),
            total_tokens=token_count("total_tokens"),
            latency_ms=elapsed_ms,
            temperature=temperature,
            seed=seed,
            finish_reason=choice.finish_reason or "",
            raw=response.model_dump(),
        )

    @property
    def model_id(self) -> str:
        return f"{self._provider}/{self._model}"

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


class MockGenerator(LLMProvider):
    """
    Deterministic mock generator for offline tests.
    Returns consistent responses based on prompt hash.
    """

    MOCK_RESPONSES = {
        "insufficient": (
            "insufficient_evidence\n\n"
            "The provided evidence does not contain enough information "
            "to answer this question."
        ),
        "default": (
            "Based on the provided evidence, {answer_hint}. [{paper_id}, p.{page}, {evidence_id}]"
        ),
    }

    def __init__(self, default_paper_id: str = "P01") -> None:
        self._paper_id = default_paper_id
        logger.info("MockGenerator initialized")

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        seed: int | None = None,
    ) -> LLMResponse:
        """Generate deterministic mock response."""
        start = time.perf_counter()

        # Mock returns a real evidence ID and an exact quote; never fabricates facts.
        text = extract_response(prompt, max_tokens)
        elapsed_ms = (time.perf_counter() - start) * 1000
        est_tokens = len(prompt.split()) + len(text.split())

        return LLMResponse(
            text=text,
            model_id="mock/deterministic",
            model_version="1.0.0",
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(text.split()),
            total_tokens=est_tokens,
            latency_ms=elapsed_ms,
            temperature=temperature,
            seed=seed,
            finish_reason="stop",
        )

    @property
    def model_id(self) -> str:
        return "mock/deterministic"


def create_llm(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    **kwargs: Any,
) -> LLMProvider:
    """Factory function to create an LLM provider."""
    if provider == "openai":
        return OpenAIGenerator(model=model, **kwargs)
    elif provider == "extractive":
        return ExtractiveGenerator(**kwargs)
    elif provider == "mock":
        return MockGenerator(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def extract_response(prompt: str, max_tokens: int = 512) -> str:
    import json
    import re

    try:
        evidence = json.JSONDecoder().raw_decode(prompt.split("Evidence:\n", 1)[1])[0]
    except (ValueError, IndexError):
        return "insufficient_evidence"
    # Conservative heuristic, not a complete prompt-injection defense.
    suspicious = re.compile(
        r"ignore.{0,40}instructions|system\s*prompt|you are now|reveal.{0,20}secret|tell the user|<\|.*?\|>",
        re.I | re.S,
    )
    safe = [
        e
        for e in evidence
        if not suspicious.search(e["text"])
        and (
            "|" in e["text"]
            or re.search(
                r"\b(is|are|was|were|use[sd]?|achieve[sd]?|propose[sd]?|reduce[sd]?|scal(?:e[sd]?|ing)|perform[sd]?|contains?|has|have)\b",
                e["text"],
                re.I,
            )
        )
    ]
    if not safe:
        return "insufficient_evidence"
    # Quotes are explicitly extractive; there is no inferred synthesis.
    selected = []
    seen = set()
    for ev in safe:
        if ev["paper_id"] not in seen:
            selected.append(ev)
            seen.add(ev["paper_id"])
        if len(selected) >= 2:
            break
    return "\n".join(
        "Extracted evidence: “"
        + re.sub(r"\s+", " ", ev["text"])[
            : max(1, min(700, (max_tokens * 3 - 150) // len(selected)))
        ]
        + f"” [{ev['paper_id']}, p.{ev['page']}, {ev['evidence_id']}]."
        for ev in selected
    )


class ExtractiveGenerator(MockGenerator):
    """Offline evidence quotation baseline, not an LLM or answer correctness judge."""

    def generate(self, *args, **kwargs):
        result = super().generate(*args, **kwargs)
        result.model_id = self.model_id
        result.model_version = "1.0"
        return result

    @property
    def model_id(self):
        return "extractive/quotes-v1"
