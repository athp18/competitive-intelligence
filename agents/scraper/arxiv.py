"""ArXiv scraper via the ArXiv API."""
import xml.etree.ElementTree as ET
import structlog

from agents.scraper.base import BaseScraperAgent

log = structlog.get_logger()

ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArXivSubAgent(BaseScraperAgent):
    name = "arxiv"

    async def fetch(self, config: dict) -> list[dict]:
        """config keys: query (str), max_results (int)."""
        query = config.get("query", "")
        if not query:
            return []

        items: list[dict] = []
        try:
            resp = await self.get(
                ARXIV_API,
                params={
                    "search_query": query,
                    "max_results": config.get("max_results", 50 if config.get("_initial") else 10),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
            )
            root = ET.fromstring(resp.text)
            for entry in root.findall("atom:entry", NS):
                def _t(tag: str) -> str:
                    el = entry.find(tag, NS)
                    return el.text.strip() if el is not None and el.text else ""

                arxiv_id = _t("atom:id").split("/abs/")[-1]
                items.append({
                    "type": "arxiv_paper",
                    "title": _t("atom:title").replace("\n", " "),
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                    "date": _t("atom:published")[:10],
                    "abstract": _t("atom:summary").replace("\n", " ")[:1000],
                    "authors": [
                        a.find("atom:name", NS).text
                        for a in entry.findall("atom:author", NS)
                        if a.find("atom:name", NS) is not None
                    ],
                    "arxiv_id": arxiv_id,
                })
        except Exception as e:
            log.warning("arxiv_failed", query=query, error=str(e))

        return items
