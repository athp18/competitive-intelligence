"""Alert delivery task with exponential backoff retries."""
import asyncio
from uuid import UUID

import httpx
import structlog

from tasks.celery_app import app

log = structlog.get_logger()


@app.task(
    name="tasks.alert.send_alert",
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def send_alert(self, alert_id: str, signal_id: str) -> None:
    asyncio.get_event_loop().run_until_complete(_send_alert_async(alert_id, signal_id))


async def _send_alert_async(alert_id: str, signal_id: str) -> None:
    from datetime import datetime, timezone
    from db.models import get_session_factory
    from db.queries import get_alert
    from sqlalchemy import update
    from db.models import Alert, Signal
    from sqlalchemy import select

    session_factory = get_session_factory()

    async with session_factory() as session:
        alert = await get_alert(session, UUID(alert_id))
        if not alert or not alert.active or not alert.webhook_url:
            return

        result = await session.execute(
            select(Signal).where(Signal.id == UUID(signal_id))
        )
        signal = result.scalar_one_or_none()
        if not signal:
            return

        payload = {
            "alert_id": alert_id,
            "signal_id": signal_id,
            "signal_type": signal.signal_type,
            "summary": signal.summary,
            "relevance": signal.relevance,
            "source": signal.source,
            "signal_date": str(signal.signal_date),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(alert.webhook_url, json=payload)
            resp.raise_for_status()

        await session.execute(
            update(Alert).where(Alert.id == UUID(alert_id)).values(
                last_delivery_at=datetime.now(timezone.utc),
                last_delivery_status="ok",
            )
        )
        await session.commit()
        log.info("alert_delivered", alert_id=alert_id, signal_id=signal_id)


async def check_and_fire_alerts(signal_id: str, signal_type: str, relevance: str) -> None:
    """Called after a new signal is stored — checks all active alert conditions."""
    from db.models import get_session_factory
    from db.queries import list_alerts

    session_factory = get_session_factory()
    async with session_factory() as session:
        alerts = await list_alerts(session)

    for alert in alerts:
        condition: dict = alert.condition or {}
        if condition.get("signal_type") and condition["signal_type"] != signal_type:
            continue
        if condition.get("relevance") and condition["relevance"] != relevance:
            continue
        send_alert.apply_async(args=[str(alert.id), signal_id])
