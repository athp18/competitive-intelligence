"""Lever public jobs API scraper."""
import structlog

from agents.scraper.base import BaseScraperAgent

log = structlog.get_logger()

LEVER_API = "https://api.lever.co/v0/postings"


class LeverSubAgent(BaseScraperAgent):
    name = "lever"

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: slug (str)."""
        slug = config.get("slug")
        if not slug:
            log.info("lever_no_slug_skipped")
            return []

        items: list[dict] = []
        try:
            resp = await self.get(f"{LEVER_API}/{slug}?mode=json")
            for posting in resp.json():
                items.append({
                    "type": "job_posting",
                    "title": posting.get("text", ""),
                    "url": posting.get("hostedUrl", ""),
                    "date": None,
                    "department": (posting.get("categories") or {}).get("department", ""),
                    "location": (posting.get("categories") or {}).get("location", ""),
                    "team": (posting.get("categories") or {}).get("team", ""),
                    "commitment": (posting.get("categories") or {}).get("commitment", ""),
                    "slug": slug,
                    "platform": "lever",
                    "id": posting.get("id"),
                })
        except Exception as e:
            log.warning("lever_failed", slug=slug, error=str(e))

        return items
