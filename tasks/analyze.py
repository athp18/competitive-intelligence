"""Analysis and comparison tasks."""
import asyncio
from uuid import UUID

import structlog

from tasks.celery_app import app

log = structlog.get_logger()


@app.task(name="tasks.analyze.run_all_analysis")
def run_all_analysis() -> None:
    asyncio.get_event_loop().run_until_complete(_run_all_async())


async def _run_all_async() -> None:
    from agents.analysis import AnalysisAgent
    from db.models import get_session_factory
    from db.queries import list_targets

    session_factory = get_session_factory()
    agent = AnalysisAgent()

    async with session_factory() as session:
        targets = await list_targets(session)

    for target in targets:
        try:
            await agent.run_daily(target.id, target.name)
        except Exception as e:
            log.error("analysis_failed", target=target.name, error=str(e))


@app.task(name="tasks.analyze.run_compare_task")
def run_compare_task(target_a_id: str, target_b_id: str) -> str:
    return asyncio.get_event_loop().run_until_complete(
        _run_compare_async(target_a_id, target_b_id)
    )


async def _run_compare_async(target_a_id: str, target_b_id: str) -> str:
    from agents.analysis import AnalysisAgent
    from db.models import get_session_factory
    from db.queries import get_target

    session_factory = get_session_factory()
    agent = AnalysisAgent()

    async with session_factory() as session:
        target_a = await get_target(session, UUID(target_a_id))
        target_b = await get_target(session, UUID(target_b_id))

    if not target_a or not target_b:
        return "One or both targets not found."

    return await agent.run_compare(
        target_a.id, target_a.name,
        target_b.id, target_b.name,
    )
