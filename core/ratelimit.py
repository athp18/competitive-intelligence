"""Redis-backed token bucket rate limiter, one bucket per domain."""
import asyncio
import time
from urllib.parse import urlparse

import redis.asyncio as aioredis

from core.config import get_settings

_redis: aioredis.Redis | None = None

# Per-domain min delay in seconds
DOMAIN_DELAYS: dict[str, float] = {
    "api.github.com": 0.5,
    "hn.algolia.com": 0.2,
    "newsapi.org": 0.5,
    "boards.greenhouse.io": 0.3,
    "api.lever.co": 0.3,
    "export.arxiv.org": 1.0,
    "www.reddit.com": 2.0,
}
DEFAULT_DELAY = 1.0


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _domain(url: str) -> str:
    return urlparse(url).netloc


async def wait_for_slot(url: str) -> None:
    domain = _domain(url)
    delay = DOMAIN_DELAYS.get(domain, DEFAULT_DELAY)
    key = f"ratelimit:{domain}"
    r = _get_redis()

    while True:
        now = time.time()
        last = await r.get(key)
        if last is None or (now - float(last)) >= delay:
            await r.set(key, now, ex=int(delay * 2) + 1)
            return
        wait = delay - (now - float(last))
        await asyncio.sleep(max(wait, 0.05))
