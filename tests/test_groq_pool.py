from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from researchpilot.providers.groq_pool import GroqKeyPool, GroqPoolGenerator, GroqQuotaExhausted
from researchpilot.providers.llm import LLMResponse


class Limited(Exception):
    status_code = 429
    response = SimpleNamespace(headers={"retry-after": "10"})


def test_pool_failover_only_on_quota_and_preserves_request():
    pool = GroqKeyPool(["first", "second", "first"])
    constructor = MagicMock()
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=constructor)}):
        llm = GroqPoolGenerator(pool, "model", "vi")
        llm._json_mode = True
        with patch(
            "researchpilot.providers.llm.OpenAIGenerator.generate",
            side_effect=[Limited(), LLMResponse(text="ok", model_id="test")],
        ) as generate:
            assert llm.generate("question", system_prompt="instructions").text == "ok"
        assert generate.call_count == 2
        assert generate.call_args_list[0] == generate.call_args_list[1]
        assert llm._json_mode and pool.active == 1
        assert constructor.call_args.kwargs["api_key"] == "second"
    assert pool.choose()[0] == 1
    assert len(pool.keys) == 2


def test_no_retry_for_bad_key_or_other_errors():
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=MagicMock())}):
        llm = GroqPoolGenerator(GroqKeyPool(["first", "second"]), "model", "vi")
        with patch(
            "researchpilot.providers.llm.OpenAIGenerator.generate", side_effect=ValueError("bad")
        ) as generate:
            with pytest.raises(ValueError):
                llm.generate("question")
        assert generate.call_count == 1


def test_exhausted_pool_is_bounded_and_cooldowns_expire():
    pool = GroqKeyPool(["first", "second"])
    with (
        patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=MagicMock())}),
        patch("researchpilot.providers.groq_pool.time.monotonic", return_value=100),
    ):
        llm = GroqPoolGenerator(pool, "model", "vi")
        with patch(
            "researchpilot.providers.llm.OpenAIGenerator.generate", side_effect=Limited()
        ) as generate:
            with pytest.raises(GroqQuotaExhausted):
                llm.generate("question")
        assert generate.call_count == 2
        with pytest.raises(GroqQuotaExhausted):
            pool.choose()
    with patch("researchpilot.providers.groq_pool.time.monotonic", return_value=111):
        assert pool.choose()[0] in {0, 1}
