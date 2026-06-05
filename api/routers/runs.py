from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, verify_api_key
from db.queries import get_run, list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


def _serialize(r) -> dict:
    return {
        "id": str(r.id),
        "target_id": str(r.target_id) if r.target_id else None,
        "source": r.source,
        "status": r.status,
        "signals_new": r.signals_new,
        "signals_dup": r.signals_dup,
        "error": r.error,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


@router.post("/trigger/{target_id}", dependencies=[Depends(verify_api_key)])
async def trigger(target_id: UUID, db: AsyncSession = Depends(get_db)):
    from agents.orchestrator import Orchestrator
    orchestrator = Orchestrator()
    run_ids = await orchestrator.spawn_single(target_id)
    return {"run_ids": [str(r) for r in run_ids]}


@router.get("/{run_id}", dependencies=[Depends(verify_api_key)])
async def get_one(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = await get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize(run)


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_all(
    status: str | None = Query(None),
    target_id: UUID | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    runs = await list_runs(db, status=status, target_id=target_id, limit=limit)
    return [_serialize(r) for r in runs]
