"""HackerNews scraper via Algolia API + Who's Hiring thread parsing."""
import re
import structlog

from agents.scraper.base import BaseScraperAgent

log = structlog.get_logger()

ALGOLIA_API = "https://hn.algolia.com/api/v1"
HIRING_STORY_PATTERN = re.compile(r"Ask HN: Who is hiring\?", re.IGNORECASE)


class HNSubAgent(BaseScraperAgent):
    name = "hn"

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: query (str), include_hiring (bool)."""
        query = config.get("query", "")
        items: list[dict] = []

        if query:
            items += await self._search(query)

        if config.get("include_hiring", False):
            items += await self._fetch_hiring(query)

        return items

    async def _search(self, query: str) -> list[dict]:
        items: list[dict] = []
        try:
            resp = await self.get(
                f"{ALGOLIA_API}/search",
                params={"query": query, "tags": "story", "hitsPerPage": 20},
            )
            for hit in resp.json().get("hits", []):
                items.append({
                    "type": "hn_story",
                    "title": hit.get("title", ""),
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "date": hit.get("created_at", "")[:10],
                    "points": hit.get("points", 0),
                    "num_comments": hit.get("num_comments", 0),
                    "author": hit.get("author", ""),
                    "hn_id": hit.get("objectID"),
                })
        except Exception as e:
            log.warning("hn_search_failed", query=query, error=str(e))
        return items

    async def _fetch_hiring(self, company_query: str) -> list[dict]:
        """Parse the most recent Who's Hiring thread for company mentions."""
        items: list[dict] = []
        try:
            # Find the latest "Who is hiring?" story
            resp = await self.get(
                f"{ALGOLIA_API}/search",
                params={"query": "Ask HN: Who is hiring?", "tags": "story,ask_hn", "hitsPerPage": 1},
            )
            hits = resp.json().get("hits", [])
            if not hits:
                return []

            story_id = hits[0].get("objectID")
            detail = await self.get(f"{ALGOLIA_API}/items/{story_id}")
            children = detail.json().get("children", [])

            for child in children:
                text = child.get("text") or ""
                if company_query.lower() in text.lower():
                    items.append({
                        "type": "hn_hiring",
                        "title": f"HN Hiring: {text[:100]}",
                        "url": f"https://news.ycombinator.com/item?id={child.get('id')}",
                        "date": child.get("created_at", "")[:10],
                        "text": text[:2000],
                        "author": child.get("author", ""),
                    })
        except Exception as e:
            log.warning("hn_hiring_failed", error=str(e))
        return items
