"""Generate embeddings using Voyage AI (primary) or OpenAI (fallback)."""
import hashlib
import struct

import redis.asyncio as aioredis
import structlog

from core.config import get_settings

log = structlog.get_logger()

EMBEDDING_DIM = 1024
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=False)
    return _redis


def _cache_key(text: str) -> str:
    return "emb:" + hashlib.sha256(text.encode()).hexdigest()


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _unpack(data: bytes) -> list[float]:
    return list(struct.unpack(f"{EMBEDDING_DIM}f", data))


async def embed(text: str) -> list[float]:
    """Return a 1024-dim embedding, cached in Redis."""
    results = await embed_batch([text])
    return results[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Return embeddings for a list of texts, using Redis cache and a single API call for misses."""
    r = _get_redis()
    keys = [_cache_key(t) for t in texts]

    # Fetch all from cache in one pipeline
    pipe = r.pipeline()
    for key in keys:
        pipe.get(key)
    cached_values = await pipe.execute()

    results: list[list[float] | None] = [None] * len(texts)
    miss_indices: list[int] = []

    for i, cached in enumerate(cached_values):
        if cached:
            results[i] = _unpack(cached)
        else:
            miss_indices.append(i)

    if miss_indices:
        miss_texts = [texts[i] for i in miss_indices]
        vectors = await _generate_batch(miss_texts)

        pipe = r.pipeline()
        for i, vector in zip(miss_indices, vectors):
            results[i] = vector
            pipe.set(keys[i], _pack(vector), ex=7 * 86400)
        await pipe.execute()

    return results  # type: ignore[return-value]


async def _generate_batch(texts: list[str]) -> list[list[float]]:
    settings = get_settings()

    if settings.voyage_api_key:
        try:
            import voyageai
            client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
            resp = await client.embed([t[:32000] for t in texts], model="voyage-3")
            return resp.embeddings
        except Exception as e:
            log.warning("voyage_embedding_failed", error=str(e))

    if settings.openai_api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            resp = await client.embeddings.create(
                model="text-embedding-3-small",
                input=[t[:8000] for t in texts],
            )
            return [item.embedding for item in resp.data]
        except Exception as e:
            log.warning("openai_embedding_failed", error=str(e))

    log.warning("no_embedding_provider_configured", count=len(texts))
    return [[0.0] * EMBEDDING_DIM for _ in texts]
