import asyncio
import json
import logging
import random
from collections import deque
from time import time
from typing import Any, Dict, List, Optional

from groq import AsyncGroq, RateLimitError

from backend.config import settings

logger = logging.getLogger(__name__)

# Stage name derived from model: planner / research / synthesis / critic / eval
_MODEL_TO_STAGE: Dict[str, str] = {
    settings.groq_planner_model:   "planner",
    settings.groq_research_model:  "research",
    settings.groq_synthesis_model: "synthesis",
    settings.groq_critic_model:    "critic",
    settings.groq_eval_model:      "eval",
}


class GroqClient:
    """Async Groq wrapper with semaphore-based rate limiting, retry logic,
    and per-session token usage tracking via the metrics ContextVar."""

    _instance: Optional["GroqClient"] = None

    def __new__(cls) -> "GroqClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._semaphore = asyncio.Semaphore(settings.groq_max_concurrent_requests)
        self._request_timestamps: deque = deque()
        self._rpm_limit = settings.groq_rpm_limit
        self._lock = asyncio.Lock()

    async def _wait_for_rate_limit(self) -> None:
        """Wait if we are approaching the RPM limit."""
        async with self._lock:
            now = time()
            while self._request_timestamps and self._request_timestamps[0] < now - 60:
                self._request_timestamps.popleft()

            if len(self._request_timestamps) >= self._rpm_limit:
                oldest = self._request_timestamps[0]
                sleep_time = 60 - (now - oldest) + 0.5
                if sleep_time > 0:
                    logger.info(f"Rate limit: sleeping {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)

            self._request_timestamps.append(time())

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request with rate limiting and retries.
        Token usage is recorded into the current session's PipelineMetrics."""
        max_retries = settings.groq_retry_max_attempts
        base_delay = settings.groq_retry_base_delay

        for attempt in range(max_retries + 1):
            await self._wait_for_rate_limit()
            async with self._semaphore:
                try:
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if response_format:
                        kwargs["response_format"] = response_format

                    response = await self._client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content or ""

                    # Record token usage into the active session metrics
                    self._record_tokens(model, response)

                    return content

                except RateLimitError:
                    if attempt == max_retries:
                        raise
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

                except Exception:
                    if attempt == max_retries:
                        raise
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Groq error (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s",
                        exc_info=True,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError("Exhausted retries")

    async def complete_json(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a chat completion requesting JSON output, parse and return dict."""
        content = await self.complete(
            messages=messages,
            model=model,
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return json.loads(content)

    @staticmethod
    def _record_tokens(model: str, response: Any) -> None:
        """Write token counts into the current session's PipelineMetrics."""
        # Import here to avoid circular import at module load time
        from backend.core.metrics import get_metrics

        usage = getattr(response, "usage", None)
        if usage is None:
            return

        metrics = get_metrics()
        if metrics is None:
            return

        stage = _MODEL_TO_STAGE.get(model, model)
        metrics.record_tokens(
            stage=stage,
            prompt=getattr(usage, "prompt_tokens", 0),
            completion=getattr(usage, "completion_tokens", 0),
        )


groq_client = GroqClient()
