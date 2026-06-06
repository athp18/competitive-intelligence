"""Career page scraper with dynamic URL detection."""
import trafilatura
import structlog

from agents.scraper.base import BaseScraperAgent
from core.llm import LLMClient, MODEL_HAIKU

log = structlog.get_logger()

URL_CANDIDATES = [
    "https://{domain}/careers",
    "https://{domain}/jobs",
    "https://careers.{domain}",
    "https://jobs.{domain}",
    "https://{domain}/about/careers",
    "https://{domain}/company/careers",
]


class CareersSubAgent(BaseScraperAgent):
    name = "careers"

    async def fetch(self, config: dict) -> list[dict]:
        """
        config keys:
          - url: careers page URL (optional, auto-detected if absent)
          - domain: company domain used for heuristic detection (e.g. 'rivian.com')
          - _target_id: injected by crawl task
          - _target_name: injected by crawl task
        """
        target_id = config.get("_target_id")
        target_name = config.get("_target_name", "")
        url = config.get("url")

        if not url:
            url = await self._detect_url(target_name, config.get("domain", ""))
            if url and target_id:
                await self._persist_url(target_id, url)

        if not url:
            log.warning("careers_url_not_found", target=target_name)
            return []

        return await self._scrape(url, target_name)

    async def _detect_url(self, company_name: str, domain: str) -> str | None:
        # Try common URL patterns first
        if domain:
            for template in URL_CANDIDATES:
                candidate = template.format(domain=domain)
                try:
                    resp = await self.get(candidate)
                    if resp.status_code == 200:
                        log.info("careers_url_found_heuristic", url=candidate)
                        return candidate
                except Exception:
                    continue

        # Fall back to Haiku
        return await self._llm_detect(company_name)

    async def _llm_detect(self, company_name: str) -> str | None:
        if not company_name:
            return None
        llm = LLMClient()
        response = await llm.call(
            prompt=(
                f"What is the careers or jobs page URL for {company_name}? "
                "Return only the full URL starting with https://. "
                "If you are not confident, return the word 'unknown'."
            ),
            model=MODEL_HAIKU,
            caller="careers_scraper:url_detect",
            max_tokens=64,
        )
        url = llm.extract_text(response).strip()
        if not url.startswith("http"):
            return None
        try:
            resp = await self.get(url)
            if resp.status_code == 200:
                log.info("careers_url_found_llm", url=url, company=company_name)
                return url
        except Exception:
            pass
        return None

    async def _persist_url(self, target_id: str, url: str) -> None:
        from uuid import UUID
        from db.models import get_session_factory
        from db.queries import get_target, update_target

        session_factory = get_session_factory()
        async with session_factory() as session:
            target = await get_target(session, UUID(target_id))
            if target:
                sources = dict(target.sources or {})
                sources.setdefault("careers", {})["url"] = url
                await update_target(session, UUID(target_id), {"sources": sources})
        log.info("careers_url_persisted", target_id=target_id, url=url)

    async def _scrape(self, url: str, company_name: str) -> list[dict]:
        try:
            resp = await self.get(url)
            text = trafilatura.extract(resp.text) or ""
            if not text:
                # trafilatura got nothing (likely JS-rendered) — keep raw stripped text
                text = resp.text[:8000]

            return [{
                "type": "careers_page",
                "title": f"{company_name} Careers",
                "url": url,
                "content": text[:6000],
                "date": None,
            }]
        except Exception as e:
            log.warning("careers_scrape_failed", url=url, error=str(e))
            return []
