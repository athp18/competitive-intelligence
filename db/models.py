import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from core.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Target(Base):
    __tablename__ = "targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)           # company, topic, person, repo
    aliases = Column(ARRAY(Text), default=[])
    sources = Column(JSONB, default={})            # {"github": {"repo": "..."}}
    schedule = Column(JSONB, default={})           # {"github": "daily", "news": "6h"}
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    signals = relationship("Signal", back_populates="target", lazy="select")
    runs = relationship("Run", back_populates="target", lazy="select")
    reports = relationship("Report", back_populates="target", lazy="select")
    alerts = relationship("Alert", back_populates="target", lazy="select")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"), nullable=True)
    pending_resolution = Column(Boolean, default=False)
    source = Column(Text, nullable=False)
    signal_type = Column(Text, nullable=False)    # hiring, research, product, funding, mention
    summary = Column(Text, nullable=False)
    relevance = Column(Text)                       # high, medium, low
    raw_url = Column(Text)
    raw_hash = Column(Text)
    signal_date = Column(Date)
    embedding = Column(Vector(1024))
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    target = relationship("Target", back_populates="signals")


class Run(Base):
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"), nullable=True)
    source = Column(Text)
    status = Column(Text, default="pending")      # pending, running, done, failed
    signals_new = Column(Integer, default=0)
    signals_dup = Column(Integer, default=0)
    error = Column(Text)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    target = relationship("Target", back_populates="runs")


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"))
    report_type = Column(Text)                    # weekly_digest, trend, comparison
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    target = relationship("Target", back_populates="reports")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"))
    condition = Column(JSONB, default={})          # {"signal_type": "funding", "relevance": "high"}
    webhook_url = Column(Text)
    last_delivery_at = Column(DateTime(timezone=True))
    last_delivery_status = Column(Text)            # ok, failed, retrying
    active = Column(Boolean, default=True)

    target = relationship("Target", back_populates="alerts")


# --- Engine & session factory ---

_engine = None
_async_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        _engine = create_async_engine(
            get_settings().database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker
        _async_session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _async_session_factory
