"""Bounded failover for server-owned Groq keys; never expose key values."""

import logging
import threading
import time

from pydantic import SecretStr

from researchpilot.providers.llm import OpenAIGenerator

logger = logging.getLogger(__name__)

_MAX_COOLDOWN_WAIT = 90  # seconds; longest we block waiting for a key to recover


class GroqQuotaExhausted(RuntimeError):
    pass


class GroqKeyPool:
    def __init__(self, keys):
        self.keys = [SecretStr(k) for k in dict.fromkeys(k.strip() for k in keys if k.strip())]
        self.cooldowns = {}
        self.lock = threading.Lock()
        self.active = 0

    def choose(self, excluded=(), max_wait: float = _MAX_COOLDOWN_WAIT):
        """Pick the next available key, waiting for cooldown recovery if needed.

        When every non-excluded key is on cooldown the method sleeps until the
        shortest cooldown expires (up to *max_wait* seconds total) then retries.
        Raises ``GroqQuotaExhausted`` only after the wait budget is exhausted.
        """
        if not self.keys:
            raise GroqQuotaExhausted("No Groq keys configured")
        deadline = time.monotonic() + max_wait
        while True:
            now = time.monotonic()
            with self.lock:
                # First pass: return a ready key immediately.
                for offset in range(len(self.keys)):
                    index = (self.active + offset) % len(self.keys)
                    if index not in excluded and self.cooldowns.get(index, 0) <= now:
                        self.active = index
                        return index, self.keys[index].get_secret_value()
                # All keys busy — find the earliest recovery among non-excluded keys.
                soonest = None
                for idx in range(len(self.keys)):
                    if idx in excluded:
                        continue
                    cd = self.cooldowns.get(idx, 0)
                    if soonest is None or cd < soonest:
                        soonest = cd
            # No non-excluded key exists at all.
            if soonest is None:
                raise GroqQuotaExhausted("All Groq keys attempted in this request")
            wait = soonest - time.monotonic()
            if wait <= 0:
                # Cooldown just expired — retry immediately.
                continue
            if time.monotonic() + wait > deadline:
                raise GroqQuotaExhausted(
                    f"All Groq keys rate-limited; shortest cooldown {wait:.0f}s exceeds budget"
                )
            logger.info("All pool keys rate-limited; waiting %.1fs for cooldown", wait)
            time.sleep(min(wait + 0.1, deadline - time.monotonic()))

    def limited(self, index, error):
        try:
            delay = float(error.response.headers.get("retry-after", 60))
        except (AttributeError, TypeError, ValueError):
            delay = 60
        with self.lock:
            self.cooldowns[index] = time.monotonic() + max(1, min(delay, 86400))


class GroqPoolGenerator(OpenAIGenerator):
    def __init__(self, pool, model, language):
        self.pool = pool
        self.key_index, key = pool.choose()
        super().__init__(model=model, api_key=key, provider="groq", language=language)

    def generate(self, *args, **kwargs):
        attempted = set()
        while True:
            attempted.add(self.key_index)
            try:
                return super().generate(*args, **kwargs)
            except Exception as exc:
                if getattr(exc, "status_code", None) != 429:
                    raise
                self.pool.limited(self.key_index, exc)
                try:
                    index, key = self.pool.choose(attempted)
                except GroqQuotaExhausted:
                    # Try each key at most once per generation. A later request may
                    # wait for cooldown, but persistent 429s must end this request.
                    raise exc from None
                self._client.close()
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=key,
                    timeout=60,
                    max_retries=0,
                    base_url="https://api.groq.com/openai/v1",
                )
                self.key_index = index
