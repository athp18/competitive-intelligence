"""Base scraper agent with retry logic and rate limiting."""
import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from core.ratelimit import wait_for_slot

log = structlog.get_logger()


class BaseScraperAgent(ABC):
    name: str = "base"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "CIE-Bot/1.0 (+https://github.com/athp18/competitive-intelligence)"},
            )
        return self._client

    async def get(self, url: str, **kwargs) -> httpx.Response:
        await wait_for_slot(url)
        client = await self._get_client()
        resp = await client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    @abstractmethod
    async def fetch(self, config: dict) -> list[dict]:
        """Return list of raw item dicts for a given target config."""
        ...

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
