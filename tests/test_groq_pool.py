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
            with pytest.raises(Limited):
                llm.generate("question")
        assert generate.call_count == 2
        with pytest.raises(GroqQuotaExhausted):
            pool.choose(max_wait=0)
    with patch("researchpilot.providers.groq_pool.time.monotonic", return_value=111):
        assert pool.choose()[0] in {0, 1}


def test_pool_waits_for_recovery_within_budget():
    pool = GroqKeyPool(["first"])
    clock = [100.0]

    def advance(seconds):
        clock[0] += seconds

    with (
        patch("researchpilot.providers.groq_pool.time.monotonic", side_effect=lambda: clock[0]),
        patch("researchpilot.providers.groq_pool.time.sleep", side_effect=advance) as sleep,
    ):
        pool.limited(0, Limited())
        assert pool.choose(max_wait=11)[0] == 0
        sleep.assert_called_once()
        assert clock[0] >= 110


def test_pool_does_not_sleep_beyond_wait_budget():
    pool = GroqKeyPool(["first"])
    with (
        patch("researchpilot.providers.groq_pool.time.monotonic", return_value=100),
        patch("researchpilot.providers.groq_pool.time.sleep") as sleep,
    ):
        pool.limited(0, Limited())
        with pytest.raises(GroqQuotaExhausted):
            pool.choose(max_wait=5)
        sleep.assert_not_called()
