"""Greenhouse public jobs API scraper."""
import structlog

from agents.scraper.base import BaseScraperAgent

log = structlog.get_logger()

GREENHOUSE_API = "https://boards.greenhouse.io/v1/boards"


class GreenhouseSubAgent(BaseScraperAgent):
    name = "greenhouse"

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: slug (str)."""
        slug = config.get("slug")
        if not slug:
            log.info("greenhouse_no_slug_skipped")
            return []

        items: list[dict] = []
        try:
            resp = await self.get(f"{GREENHOUSE_API}/{slug}/jobs?content=true")
            for job in resp.json().get("jobs", []):
                metadata = job.get("metadata", [])
                items.append({
                    "type": "job_posting",
                    "title": job.get("title", ""),
                    "url": job.get("absolute_url", ""),
                    "date": (job.get("updated_at") or "")[:10],
                    "department": (job.get("departments") or [{}])[0].get("name", ""),
                    "location": (job.get("offices") or [{}])[0].get("name", ""),
                    "slug": slug,
                    "platform": "greenhouse",
                    "id": job.get("id"),
                })
        except Exception as e:
            log.warning("greenhouse_failed", slug=slug, error=str(e))

        return items
