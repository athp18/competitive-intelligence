"""NewsAPI scraper."""
import structlog

from agents.scraper.base import BaseScraperAgent
from core.config import get_settings

log = structlog.get_logger()

NEWS_API = "https://newsapi.org/v2"


class NewsSubAgent(BaseScraperAgent):
    name = "news"

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: query (str), domains (list[str])."""
        query = config.get("query", "")
        if not query:
            return []

        api_key = get_settings().news_api_key
        if not api_key:
            log.warning("newsapi_key_missing")
            return []

        items: list[dict] = []
        params: dict = {
            "q": query,
            "apiKey": api_key,
            "pageSize": 20,
            "language": "en",
            "sortBy": "publishedAt",
        }
        if config.get("domains"):
            params["domains"] = ",".join(config["domains"])

        try:
            resp = await self.get(f"{NEWS_API}/everything", params=params)
            data = resp.json()
            if data.get("status") != "ok":
                log.warning("newsapi_error", query=query, code=data.get("code"), message=data.get("message"))
                return []
            articles = data.get("articles", [])
            log.info("newsapi_results", query=query, total=data.get("totalResults", 0), returned=len(articles))
            for article in articles:
                items.append({
                    "type": "news_article",
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "date": (article.get("publishedAt") or "")[:10],
                    "description": article.get("description") or "",
                    "source": article.get("source", {}).get("name", ""),
                    "content": (article.get("content") or "")[:1000],
                })
        except Exception as e:
            log.warning("newsapi_failed", query=query, error=str(e))

        return items
