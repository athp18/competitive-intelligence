from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, verify_api_key
from db.queries import list_signals

router = APIRouter(prefix="/targets/{target_id}/signals", tags=["signals"])


def _serialize(s) -> dict:
    return {
        "id": str(s.id),
        "target_id": str(s.target_id) if s.target_id else None,
        "source": s.source,
        "signal_type": s.signal_type,
        "summary": s.summary,
        "relevance": s.relevance,
        "raw_url": s.raw_url,
        "signal_date": s.signal_date.isoformat() if s.signal_date else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_for_target(
    target_id: UUID,
    signal_type: str | None = Query(None),
    relevance: str | None = Query(None),
    days: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    signals = await list_signals(
        db,
        target_id=target_id,
        signal_type=signal_type,
        relevance=relevance,
        days=days,
        limit=limit,
        offset=offset,
    )
    return [_serialize(s) for s in signals]
