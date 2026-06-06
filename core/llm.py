"""Central LLM client with per-caller logging, hard limits, and Redis call counting."""
import json
import time
from typing import Any

import anthropic
import redis.asyncio as aioredis
import structlog

from core.config import get_settings

log = structlog.get_logger()

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"

_redis: aioredis.Redis | None = None
_anthropic: anthropic.AsyncAnthropic | None = None

DAY_KEY = lambda: f"llm:calls:{int(time.time() // 86400)}"  # noqa: E731


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _get_client() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _anthropic


class LLMLimitExceeded(Exception):
    pass


class LLMClient:
    def __init__(self, run_id: str | None = None):
        self._run_calls = 0
        self._run_id = run_id
        self._settings = get_settings()

    async def call(
        self,
        *,
        prompt: str,
        model: str = MODEL_HAIKU,
        caller: str,
        system: str | None = None,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        messages: list[dict] | None = None,
    ) -> anthropic.types.Message:
        await self._check_limits()

        r = _get_redis()
        await r.incr(DAY_KEY())
        await r.expire(DAY_KEY(), 90000)  # 25 h TTL
        self._run_calls += 1

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        if messages is not None:
            kwargs["messages"] = messages
        else:
            kwargs["messages"] = [{"role": "user", "content": prompt}]

        t0 = time.monotonic()
        response = await _get_client().messages.create(**kwargs)
        elapsed = time.monotonic() - t0

        log.info(
            "llm_call",
            caller=caller,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            elapsed_s=round(elapsed, 2),
            run_id=self._run_id,
        )
        return response

    async def _check_limits(self) -> None:
        settings = self._settings
        if self._run_id and self._run_calls >= settings.max_llm_calls_per_run:
            raise LLMLimitExceeded(
                f"Run {self._run_id} hit max_llm_calls_per_run={settings.max_llm_calls_per_run}"
            )
        r = _get_redis()
        day_calls = int(await r.get(DAY_KEY()) or 0)
        if day_calls >= settings.max_llm_calls_per_day:
            raise LLMLimitExceeded(
                f"Daily LLM call limit reached ({settings.max_llm_calls_per_day})"
            )

    def extract_text(self, response: anthropic.types.Message) -> str:
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def extract_json(self, response: anthropic.types.Message) -> Any:
        text = self.extract_text(response)
        if "```" in text:
            lines = text.split("\n")
            inner = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(inner)
        text = text.strip()
        # Use raw_decode to tolerate trailing content after the first JSON value
        decoder = json.JSONDecoder()
        value, _ = decoder.raw_decode(text)
        return value
