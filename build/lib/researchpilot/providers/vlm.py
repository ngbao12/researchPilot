"""
VLM (Vision Language Model) providers for ResearchPilot.

Implements caption-only fallback baseline and interface for actual VLM.
The caption-only path is a separate baseline — it does NOT claim VLM reasoning.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from researchpilot.providers.llm import LLMResponse

logger = logging.getLogger(__name__)


class VLMProvider(ABC):
    """Abstract VLM interface for processing figure crops."""

    @abstractmethod
    def describe_figure(
        self,
        image_path: str,
        caption: str = "",
        question: str = "",
    ) -> LLMResponse:
        """
        Describe or answer questions about a figure.

        Args:
            image_path: Path to the figure crop image.
            caption: Extracted caption text (if available).
            question: Optional specific question about the figure.

        Returns:
            LLMResponse with the description/answer.
        """
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Model identifier for reproducibility."""
        ...

    @property
    @abstractmethod
    def is_true_vlm(self) -> bool:
        """Whether this provider actually processes image pixels."""
        ...


class CaptionOnlyFallback(VLMProvider):
    """
    Caption-only fallback — does NOT claim VLM reasoning.

    Uses only the extracted caption text without looking at the actual image.
    This is a text-only baseline, clearly labeled as such.
    """

    def __init__(self) -> None:
        logger.info(
            "CaptionOnlyFallback initialized. This does NOT perform actual image understanding."
        )

    def describe_figure(
        self,
        image_path: str,
        caption: str = "",
        question: str = "",
    ) -> LLMResponse:
        """Return caption text without image processing."""
        if not caption:
            description = (
                "[CAPTION_FALLBACK] No caption available for this figure. "
                "Image understanding requires a VLM provider."
            )
        else:
            description = f"[CAPTION_FALLBACK] Based on the caption: {caption}"

        return LLMResponse(
            text=description,
            model_id="caption-only-fallback",
            model_version="1.0.0",
            prompt_tokens=len(caption.split()),
            completion_tokens=len(description.split()),
            total_tokens=len(caption.split()) + len(description.split()),
            latency_ms=0.1,
        )

    @property
    def model_id(self) -> str:
        return "caption-only-fallback"

    @property
    def is_true_vlm(self) -> bool:
        return False


class OpenAIVisionProvider(VLMProvider):
    """
    OpenAI Vision API-based VLM (stretch goal).

    Actually processes figure crops using a vision-capable model.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
            self._model = model
            self._available = True
            logger.info("OpenAI Vision provider initialized: model=%s", model)
        except Exception as e:
            self._available = False
            logger.warning("OpenAI Vision provider unavailable: %s", e)

    def describe_figure(
        self,
        image_path: str,
        caption: str = "",
        question: str = "",
    ) -> LLMResponse:
        """Describe figure using OpenAI Vision API."""
        import base64
        import time

        if not self._available:
            return CaptionOnlyFallback().describe_figure(image_path, caption, question)

        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            logger.warning("Image not found: %s, falling back to caption", image_path)
            return CaptionOnlyFallback().describe_figure(image_path, caption, question)

        with open(image_path_obj, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        mime = "image/png" if image_path_obj.suffix == ".png" else "image/jpeg"

        prompt_text = "Describe this scientific figure in detail."
        if caption:
            prompt_text += f"\n\nCaption: {caption}"
        if question:
            prompt_text = f"Answer the following question about this figure: {question}"
            if caption:
                prompt_text += f"\n\nCaption: {caption}"

        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{image_data}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=512,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            text=choice.message.content or "",
            model_id=f"openai-vision/{self._model}",
            model_version=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=elapsed_ms,
        )

    @property
    def model_id(self) -> str:
        return f"openai-vision/{self._model}"

    @property
    def is_true_vlm(self) -> bool:
        return True


def create_vlm(
    provider: str = "caption_fallback",
    **kwargs: Any,
) -> VLMProvider:
    """Factory function to create a VLM provider."""
    if provider == "caption_fallback":
        return CaptionOnlyFallback()
    elif provider == "openai_vision":
        return OpenAIVisionProvider(**kwargs)
    else:
        raise ValueError(f"Unknown VLM provider: {provider}")
