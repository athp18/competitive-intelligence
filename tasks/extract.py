"""Extraction and entity resolution tasks."""
import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog

from tasks.celery_app import app

log = structlog.get_logger()


@app.task(name="tasks.extract.extract_signals", bind=True)
def extract_signals(
    self,
    target_id: str,
    run_id: str,
    source: str,
    raw_items: list[dict],
    target_name: str,
) -> None:
    asyncio.get_event_loop().run_until_complete(
        _extract_async(target_id, run_id, source, raw_items, target_name)
    )


async def _extract_async(
    target_id: str,
    run_id: str,
    source: str,
    raw_items: list[dict],
    target_name: str,
) -> None:
    from agents.extraction import ExtractionAgent
    from db.models import get_session_factory
    from db.queries import create_signal, signal_exists, update_run

    session_factory = get_session_factory()
    agent = ExtractionAgent(target_name=target_name, run_id=run_id)

    try:
        signals = await agent.extract(raw_items, source=source, target_id=UUID(target_id))
        signals = await agent.embed_and_attach(signals)

        new_count = 0
        dup_count = 0

        async with session_factory() as session:
            for sig in signals:
                raw_hash = sig.get("raw_hash")
                if raw_hash and await signal_exists(session, raw_hash):
                    dup_count += 1
                    continue

                # Convert string target_id back to UUID for DB
                if sig.get("target_id"):
                    sig["target_id"] = UUID(sig["target_id"])

                await create_signal(session, sig)
                new_count += 1

            await update_run(session, UUID(run_id), {
                "status": "done",
                "signals_new": new_count,
                "signals_dup": dup_count,
                "finished_at": datetime.now(timezone.utc),
            })

        log.info("extraction_complete", run_id=run_id, new=new_count, dup=dup_count)

        # Trigger entity resolution for any pending signals
        if new_count > 0:
            resolve_entities.apply_async(queue="llm")

    except Exception as e:
        log.error("extraction_failed", run_id=run_id, error=str(e))
        async with session_factory() as session:
            await update_run(session, UUID(run_id), {
                "status": "failed",
                "error": str(e),
                "finished_at": datetime.now(timezone.utc),
            })
        raise


@app.task(name="tasks.extract.resolve_entities")
def resolve_entities() -> None:
    asyncio.get_event_loop().run_until_complete(_resolve_async())


async def _resolve_async() -> None:
    from agents.entity_resolution import EntityResolutionAgent
    from db.models import get_session_factory
    from db.queries import get_pending_signals, list_targets, resolve_signal

    session_factory = get_session_factory()
    agent = EntityResolutionAgent()

    async with session_factory() as session:
        pending = await get_pending_signals(session)
        targets = await list_targets(session)

        if not pending:
            return

        resolutions = await agent.resolve_all(pending, targets)

        for signal_id, target_id in resolutions.items():
            if target_id:
                await resolve_signal(session, signal_id, target_id)

    log.info("entity_resolution_complete", resolved=sum(1 for v in resolutions.values() if v))
