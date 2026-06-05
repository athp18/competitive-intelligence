from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, verify_api_key
from db.queries import list_reports

router = APIRouter(prefix="/targets/{target_id}/reports", tags=["reports"])


def _serialize(r) -> dict:
    return {
        "id": str(r.id),
        "target_id": str(r.target_id),
        "report_type": r.report_type,
        "content": r.content,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_for_target(target_id: UUID, db: AsyncSession = Depends(get_db)):
    reports = await list_reports(db, target_id)
    return [_serialize(r) for r in reports]
