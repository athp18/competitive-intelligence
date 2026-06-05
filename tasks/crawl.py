"""Crawl tasks: fetch raw data from sources, hand off to extraction."""
import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog

from tasks.celery_app import app

log = structlog.get_logger()

SCRAPER_MAP = {
    "github": "agents.scraper.github.GitHubSubAgent",
    "hn": "agents.scraper.hn.HNSubAgent",
    "news": "agents.scraper.news.NewsSubAgent",
    "greenhouse": "agents.scraper.greenhouse.GreenhouseSubAgent",
    "lever": "agents.scraper.lever.LeverSubAgent",
    "arxiv": "agents.scraper.arxiv.ArXivSubAgent",
}


def _import_scraper(dotted_path: str):
    module_path, cls_name = dotted_path.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


@app.task(name="tasks.crawl.crawl_target", bind=True, max_retries=3)
def crawl_target(self, target_id: str, run_id: str, source: str) -> None:
    asyncio.get_event_loop().run_until_complete(
        _crawl_target_async(target_id, run_id, source)
    )


async def _crawl_target_async(target_id: str, run_id: str, source: str) -> None:
    from db.models import get_session_factory
    from db.queries import get_target, update_run

    session_factory = get_session_factory()

    async with session_factory() as session:
        target = await get_target(session, UUID(target_id))
        if not target:
            log.error("crawl_target_not_found", target_id=target_id)
            return
        await update_run(session, UUID(run_id), {"status": "running"})

    try:
        scraper_path = SCRAPER_MAP.get(source)
        if not scraper_path:
            raise ValueError(f"Unknown source: {source}")

        ScraperClass = _import_scraper(scraper_path)
        scraper = ScraperClass()

        source_config = (target.sources or {}).get(source, {})
        raw_items = await scraper.fetch(source_config)
        await scraper.close()

        log.info("crawl_complete", target=target.name, source=source, items=len(raw_items))

        if raw_items:
            from tasks.extract import extract_signals
            extract_signals.apply_async(
                args=[target_id, run_id, source, raw_items, target.name],
                queue="llm",
            )
        else:
            async with session_factory() as session:
                await update_run(session, UUID(run_id), {
                    "status": "done",
                    "finished_at": datetime.now(timezone.utc),
                })

    except Exception as e:
        log.error("crawl_failed", target_id=target_id, source=source, error=str(e))
        async with session_factory() as session:
            await update_run(session, UUID(run_id), {
                "status": "failed",
                "error": str(e),
                "finished_at": datetime.now(timezone.utc),
            })
        raise


@app.task(name="tasks.crawl.crawl_all")
def crawl_all(source: str) -> None:
    asyncio.get_event_loop().run_until_complete(_crawl_all_async(source))


async def _crawl_all_async(source: str) -> None:
    from agents.orchestrator import Orchestrator
    orchestrator = Orchestrator()
    run_ids = await orchestrator.spawn_crawls(source_filter=source)
    log.info("crawl_all_spawned", source=source, runs=len(run_ids))
