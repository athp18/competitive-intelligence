"""Google News RSS scraper — no API key required."""
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import structlog

from agents.scraper.base import BaseScraperAgent

log = structlog.get_logger()

RSS_URL = "https://news.google.com/rss/search"


class GoogleNewsSubAgent(BaseScraperAgent):
    name = "googlenews"

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: query (str), limit (int, default 20)."""
        query = config.get("query", "")
        if not query:
            return []

        items: list[dict] = []
        try:
            resp = await self.get(RSS_URL, params={
                "q": query,
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en",
            })
            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            if channel is None:
                return []

            limit = config.get("limit", 20)
            for item in channel.findall("item")[:limit]:
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                description = item.findtext("description") or ""
                pub_date = item.findtext("pubDate") or ""
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else ""

                date_str = ""
                if pub_date:
                    try:
                        date_str = parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                items.append({
                    "type": "news_article",
                    "title": title,
                    "url": link,
                    "date": date_str,
                    "description": description[:500],
                    "source": source_name,
                })
        except Exception as e:
            log.warning("googlenews_failed", query=query, error=str(e))

        log.info("googlenews_fetched", query=query, count=len(items))
        return items
