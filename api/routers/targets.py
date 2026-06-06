from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, verify_api_key
from db.queries import create_target, get_target, list_targets, list_signals, update_target

router = APIRouter(prefix="/targets", tags=["targets"])


class TargetCreate(BaseModel):
    name: str
    type: str  # company, topic, person, repo
    aliases: list[str] = []
    sources: dict = {}
    schedule: dict = {}


class TargetUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    sources: dict | None = None
    schedule: dict | None = None
    active: bool | None = None


def _serialize(target) -> dict:
    return {
        "id": str(target.id),
        "name": target.name,
        "type": target.type,
        "aliases": target.aliases or [],
        "sources": target.sources or {},
        "schedule": target.schedule or {},
        "active": target.active,
        "created_at": target.created_at.isoformat() if target.created_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def create(body: TargetCreate, db: AsyncSession = Depends(get_db)):
    import uuid
    target = await create_target(db, {
        "id": uuid.uuid4(),
        "name": body.name,
        "type": body.type,
        "aliases": body.aliases,
        "sources": body.sources,
        "schedule": body.schedule,
    })
    return _serialize(target)


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_all(db: AsyncSession = Depends(get_db)):
    targets = await list_targets(db)
    return [_serialize(t) for t in targets]


@router.get("/{target_id}", dependencies=[Depends(verify_api_key)])
async def get_one(target_id: UUID, db: AsyncSession = Depends(get_db)):
    target = await get_target(db, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    signals = await list_signals(db, target_id=target_id, days=7, limit=5)
    result = _serialize(target)
    result["recent_signals"] = [
        {"type": s.signal_type, "summary": s.summary, "relevance": s.relevance}
        for s in signals
    ]
    return result


@router.put("/{target_id}", dependencies=[Depends(verify_api_key)])
async def update(target_id: UUID, body: TargetUpdate, db: AsyncSession = Depends(get_db)):
    existing = await get_target(db, target_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Target not found")
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    target = await update_target(db, target_id, data)
    return _serialize(target)


@router.delete("/{target_id}", dependencies=[Depends(verify_api_key)])
async def deactivate(target_id: UUID, db: AsyncSession = Depends(get_db)):
    existing = await get_target(db, target_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Target not found")
    await update_target(db, target_id, {"active": False})
    # Flush extraction cache so signals are re-extracted if target is recreated
    try:
        import redis.asyncio as aioredis
        from core.config import get_settings
        r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        keys = await r.keys("extraction:*")
        if keys:
            await r.delete(*keys)
        await r.aclose()
    except Exception:
        pass
    return {"status": "deactivated"}


@router.post("/{target_id}/compare/{other_id}", dependencies=[Depends(verify_api_key)])
async def compare(target_id: UUID, other_id: UUID, db: AsyncSession = Depends(get_db)):
    from tasks.analyze import run_compare_task
    task = run_compare_task.apply_async(args=[str(target_id), str(other_id)], queue="llm")
    return {"task_id": task.id, "status": "triggered"}
