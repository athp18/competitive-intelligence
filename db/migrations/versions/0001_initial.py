"""Initial schema with pgvector

Revision ID: 0001
Revises:
Create Date: 2024-01-01
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "targets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("aliases", ARRAY(sa.Text), nullable=True),
        sa.Column("sources", JSONB, nullable=True),
        sa.Column("schedule", JSONB, nullable=True),
        sa.Column("active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", UUID(as_uuid=True), sa.ForeignKey("targets.id"), nullable=True),
        sa.Column("pending_resolution", sa.Boolean, server_default=sa.text("false")),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("signal_type", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("relevance", sa.Text, nullable=True),
        sa.Column("raw_url", sa.Text, nullable=True),
        sa.Column("raw_hash", sa.Text, nullable=True),
        sa.Column("signal_date", sa.Date, nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", UUID(as_uuid=True), sa.ForeignKey("targets.id"), nullable=True),
        sa.Column("source", sa.Text, nullable=True),
        sa.Column("status", sa.Text, server_default=sa.text("'pending'")),
        sa.Column("signals_new", sa.Integer, server_default=sa.text("0")),
        sa.Column("signals_dup", sa.Integer, server_default=sa.text("0")),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", UUID(as_uuid=True), sa.ForeignKey("targets.id")),
        sa.Column("report_type", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", UUID(as_uuid=True), sa.ForeignKey("targets.id")),
        sa.Column("condition", JSONB, nullable=True),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_delivery_status", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, server_default=sa.text("true")),
    )

    # Indexes
    op.create_index("ix_signals_target_created", "signals", ["target_id", "created_at"])
    op.create_index("ix_signals_raw_hash", "signals", ["raw_hash"])
    op.create_index(
        "ix_signals_pending",
        "signals",
        ["pending_resolution"],
        postgresql_where=sa.text("pending_resolution = true"),
    )
    # HNSW index for dev (no min rows required)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_embedding_hnsw "
        "ON signals USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("reports")
    op.drop_table("runs")
    op.drop_table("signals")
    op.drop_table("targets")
