"""Orchestrator: reads targets, spawns crawl tasks per (target, source)."""
import asyncio
import structlog
from datetime import datetime, timezone
from uuid import UUID

from db.models import get_session_factory
from db.queries import create_run, list_targets, update_run

log = structlog.get_logger()

# Maps source name -> schedule cadence (for deciding if due)
SOURCE_CADENCE = {
    "github": "daily",
    "arxiv": "daily",
    "greenhouse": "daily",
    "lever": "daily",
    "careers": "daily",
    "news": "6h",
    "googlenews": "6h",
    "hn": "6h",
    "reddit": "12h",
}


class Orchestrator:
    """Pure Python orchestrator — no LLM involved."""

    async def spawn_crawls(self, source_filter: str | None = None) -> list[UUID]:
        """Create Run records and enqueue Celery crawl tasks for all active targets."""
        from tasks.crawl import crawl_target

        session_factory = get_session_factory()
        run_ids: list[UUID] = []

        async with session_factory() as session:
            targets = await list_targets(session)

        for target in targets:
            sources_config: dict = target.sources or {}
            sources = [source_filter] if source_filter else list(sources_config.keys())

            for source in sources:
                if source not in sources_config:
                    continue

                async with session_factory() as session:
                    run = await create_run(session, {
                        "target_id": target.id,
                        "source": source,
                        "status": "pending",
                        "started_at": datetime.now(timezone.utc),
                    })
                    run_ids.append(run.id)

                # Enqueue as Celery task
                crawl_target.apply_async(
                    args=[str(target.id), str(run.id), source],
                    queue="crawl",
                )
                log.info("crawl_enqueued", target=target.name, source=source, run_id=str(run.id))

        return run_ids

    async def spawn_single(self, target_id: UUID, source: str | None = None, deep: bool = True) -> list[UUID]:
        """Manually trigger crawl for a specific target. Always deep by default."""
        from tasks.crawl import crawl_target

        session_factory = get_session_factory()
        run_ids: list[UUID] = []

        async with session_factory() as session:
            from db.queries import get_target
            target = await get_target(session, target_id)
            if not target:
                return []

            sources_config: dict = target.sources or {}
            sources = [source] if source else list(sources_config.keys())

            for src in sources:
                if src not in sources_config:
                    continue
                run = await create_run(session, {
                    "target_id": target.id,
                    "source": src,
                    "status": "pending",
                    "started_at": datetime.now(timezone.utc),
                })
                run_ids.append(run.id)
                crawl_target.apply_async(
                    args=[str(target.id), str(run.id), src, deep],
                    queue="crawl",
                )

        return run_ids
