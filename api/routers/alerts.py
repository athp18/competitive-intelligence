import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, verify_api_key
from db.queries import create_alert, get_alert, list_alerts
from sqlalchemy import update
from db.models import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    target_id: UUID
    condition: dict = {}   # {"signal_type": "funding", "relevance": "high"}
    webhook_url: str


def _serialize(a) -> dict:
    return {
        "id": str(a.id),
        "target_id": str(a.target_id),
        "condition": a.condition or {},
        "webhook_url": a.webhook_url,
        "last_delivery_at": a.last_delivery_at.isoformat() if a.last_delivery_at else None,
        "last_delivery_status": a.last_delivery_status,
        "active": a.active,
    }


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def create(body: AlertCreate, db: AsyncSession = Depends(get_db)):
    alert = await create_alert(db, {
        "id": uuid.uuid4(),
        "target_id": body.target_id,
        "condition": body.condition,
        "webhook_url": body.webhook_url,
    })
    return _serialize(alert)


@router.get("", dependencies=[Depends(verify_api_key)])
async def list_all(db: AsyncSession = Depends(get_db)):
    alerts = await list_alerts(db)
    return [_serialize(a) for a in alerts]


@router.delete("/{alert_id}", dependencies=[Depends(verify_api_key)])
async def delete(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.execute(update(Alert).where(Alert.id == alert_id).values(active=False))
    await db.commit()
    return {"status": "deleted"}
