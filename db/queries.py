"""Typed query helpers over SQLAlchemy async sessions."""
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Alert, Report, Run, Signal, Target


# --- Targets ---

async def get_target(session: AsyncSession, target_id: UUID) -> Target | None:
    result = await session.execute(select(Target).where(Target.id == target_id))
    return result.scalar_one_or_none()


async def list_targets(session: AsyncSession, active_only: bool = True) -> list[Target]:
    q = select(Target)
    if active_only:
        q = q.where(Target.active == True)
    result = await session.execute(q)
    return list(result.scalars().all())


async def find_targets_by_name(session: AsyncSession, name: str) -> list[Target]:
    """Case-insensitive match against target name and aliases."""
    pattern = f"%{name}%"
    result = await session.execute(
        select(Target).where(
            Target.active == True,
            Target.name.ilike(pattern),
        )
    )
    return list(result.scalars().all())


async def create_target(session: AsyncSession, data: dict) -> Target:
    target = Target(**data)
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


async def update_target(session: AsyncSession, target_id: UUID, data: dict) -> Target | None:
    await session.execute(update(Target).where(Target.id == target_id).values(**data))
    await session.commit()
    return await get_target(session, target_id)


# --- Signals ---

async def signal_exists(session: AsyncSession, raw_hash: str) -> bool:
    result = await session.execute(
        select(Signal.id).where(Signal.raw_hash == raw_hash).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def create_signal(session: AsyncSession, data: dict) -> Signal:
    signal = Signal(**data)
    session.add(signal)
    await session.commit()
    await session.refresh(signal)
    return signal


async def list_signals(
    session: AsyncSession,
    target_id: UUID | None = None,
    signal_type: str | None = None,
    relevance: str | None = None,
    days: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Signal]:
    q = select(Signal).order_by(Signal.created_at.desc())
    if target_id:
        q = q.where(Signal.target_id == target_id)
    if signal_type:
        q = q.where(Signal.signal_type == signal_type)
    if relevance:
        q = q.where(Signal.relevance == relevance)
    if days:
        cutoff = date.today() - timedelta(days=days)
        q = q.where(Signal.created_at >= cutoff)
    q = q.limit(limit).offset(offset)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_pending_signals(session: AsyncSession) -> list[Signal]:
    result = await session.execute(
        select(Signal).where(Signal.pending_resolution == True)
    )
    return list(result.scalars().all())


async def resolve_signal(session: AsyncSession, signal_id: UUID, target_id: UUID) -> None:
    await session.execute(
        update(Signal)
        .where(Signal.id == signal_id)
        .values(target_id=target_id, pending_resolution=False)
    )
    await session.commit()


async def semantic_search(
    session: AsyncSession,
    embedding: list[float],
    top_k: int = 10,
    target_id: UUID | None = None,
) -> list[Signal]:
    # pgvector cosine distance
    q = (
        select(Signal)
        .order_by(Signal.embedding.cosine_distance(embedding))
        .limit(top_k)
    )
    if target_id:
        q = q.where(Signal.target_id == target_id)
    result = await session.execute(q)
    return list(result.scalars().all())


# --- Runs ---

async def create_run(session: AsyncSession, data: dict) -> Run:
    run = Run(**data)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def update_run(session: AsyncSession, run_id: UUID, data: dict) -> None:
    await session.execute(update(Run).where(Run.id == run_id).values(**data))
    await session.commit()


async def get_run(session: AsyncSession, run_id: UUID) -> Run | None:
    result = await session.execute(select(Run).where(Run.id == run_id))
    return result.scalar_one_or_none()


async def list_runs(
    session: AsyncSession,
    status: str | None = None,
    target_id: UUID | None = None,
    limit: int = 50,
) -> list[Run]:
    q = select(Run).order_by(Run.started_at.desc()).limit(limit)
    if status:
        q = q.where(Run.status == status)
    if target_id:
        q = q.where(Run.target_id == target_id)
    result = await session.execute(q)
    return list(result.scalars().all())


# --- Reports ---

async def create_report(session: AsyncSession, data: dict) -> Report:
    report = Report(**data)
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_latest_report(
    session: AsyncSession, target_id: UUID, report_type: str
) -> Report | None:
    result = await session.execute(
        select(Report)
        .where(and_(Report.target_id == target_id, Report.report_type == report_type))
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_reports(session: AsyncSession, target_id: UUID) -> list[Report]:
    result = await session.execute(
        select(Report)
        .where(Report.target_id == target_id)
        .order_by(Report.created_at.desc())
    )
    return list(result.scalars().all())


# --- Alerts ---

async def create_alert(session: AsyncSession, data: dict) -> Alert:
    alert = Alert(**data)
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def list_alerts(session: AsyncSession, active_only: bool = True) -> list[Alert]:
    q = select(Alert)
    if active_only:
        q = q.where(Alert.active == True)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_alert(session: AsyncSession, alert_id: UUID) -> Alert | None:
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    return result.scalar_one_or_none()


# --- Metrics ---

async def get_metrics(session: AsyncSession) -> dict:
    today = date.today()
    signals_today = await session.execute(
        select(func.count(Signal.id)).where(func.date(Signal.created_at) == today)
    )
    runs_today = await session.execute(
        select(func.count(Run.id)).where(func.date(Run.started_at) == today)
    )
    active_targets = await session.execute(
        select(func.count(Target.id)).where(Target.active == True)
    )
    return {
        "signals_today": signals_today.scalar_one(),
        "runs_today": runs_today.scalar_one(),
        "active_targets": active_targets.scalar_one(),
    }
