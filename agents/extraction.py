"""Extraction Agent: takes raw scraped items -> structured signals via LLM."""
import hashlib
import json
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
import structlog

from core.config import get_settings
from core.dedup import content_hash
from core.embeddings import embed_batch
from core.llm import LLMClient, MODEL_HAIKU

log = structlog.get_logger()

EXTRACTION_PROMPT = """\
You are an intelligence extraction agent. Given the following content about the target "{target_name}", \
extract any meaningful signals. A signal is a specific, factual development: a product launch, \
hiring trend, research publication, funding event, or notable mention.

Return a JSON array of signals, each with:
- type: one of [hiring, research, product, funding, mention]
- summary: 1-2 sentence factual description
- relevance: high/medium/low
- date: ISO date if mentioned, else null

If there are no meaningful signals, return an empty array [].

Content:
{content}
"""

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _content_key(text: str) -> str:
    return "extraction:" + hashlib.sha256(text.encode()).hexdigest()


def _parse_date(value: str | None) -> str | None:
    """Return a YYYY-MM-DD string or None. Rejects partial dates like '2026-05'."""
    if not value:
        return None
    import re
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
        return value
    return None


def _item_to_text(item: dict) -> str:
    """Convert raw scraped item to stripped plain text for LLM."""
    parts = []
    for field in ("title", "description", "body", "abstract", "content", "text"):
        val = item.get(field)
        if val:
            parts.append(str(val)[:500])
    return "\n".join(parts)


def _batch_items(items: list[dict], max_chars: int = 6000) -> list[list[dict]]:
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_len = 0
    for item in items:
        text = _item_to_text(item)
        if current_len + len(text) > max_chars and current:
            batches.append(current)
            current = []
            current_len = 0
        current.append(item)
        current_len += len(text)
    if current:
        batches.append(current)
    return batches


class ExtractionAgent:
    def __init__(self, target_name: str, run_id: str | None = None):
        self.target_name = target_name
        self.llm = LLMClient(run_id=run_id)
        self.run_id = run_id

    async def extract(
        self,
        items: list[dict],
        source: str,
        target_id: UUID | None = None,
    ) -> list[dict]:
        """Extract signals from raw scraped items. Returns list of signal dicts."""
        all_signals: list[dict] = []
        r = _get_redis()

        batches = _batch_items(items)
        for batch in batches:
            content = "\n---\n".join(_item_to_text(i) for i in batch)
            cache_key = _content_key(content)

            cached = await r.get(cache_key)
            if cached:
                signals = json.loads(cached)
                log.info("extraction_cache_hit", count=len(signals))
            else:
                signals = await self._call_llm(content)
                await r.set(cache_key, json.dumps(signals), ex=7 * 86400)

            # Attach metadata to each signal
            for sig in signals:
                # Find the item with best matching title/url for metadata
                item = batch[0] if batch else {}
                sig["source"] = source
                sig["target_id"] = str(target_id) if target_id else None
                sig["pending_resolution"] = target_id is None
                sig["raw_url"] = item.get("url")
                sig["raw_hash"] = content_hash(
                    item.get("title", ""), item.get("url", "")
                )
                sig["signal_type"] = sig.pop("type", "mention")
                sig["signal_date"] = _parse_date(sig.pop("date", None))
                sig["metadata_"] = {"source_item": item.get("title", "")[:200]}
                all_signals.append(sig)

        return all_signals

    async def _call_llm(self, content: str) -> list[Any]:
        try:
            response = await self.llm.call(
                prompt=EXTRACTION_PROMPT.format(
                    target_name=self.target_name,
                    content=content[:6000],
                ),
                model=MODEL_HAIKU,
                caller="extraction_agent",
            )
            return self.llm.extract_json(response)
        except Exception as e:
            log.warning("extraction_llm_failed", error=str(e))
            return []

    async def embed_and_attach(self, signals: list[dict]) -> list[dict]:
        """Attach embedding vectors to signals using a single batched API call."""
        if not signals:
            return signals
        summaries = [sig.get("summary", "") for sig in signals]
        try:
            vectors = await embed_batch(summaries)
            for sig, vector in zip(signals, vectors):
                sig["embedding"] = vector
        except Exception as e:
            log.warning("embedding_batch_failed", error=str(e))
            for sig in signals:
                sig["embedding"] = None
        return signals
