"""Change embedding dimension from 1536 to 1024 (voyage-3 native)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_signals_embedding_hnsw")
    op.execute("ALTER TABLE signals ALTER COLUMN embedding TYPE vector(1024)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_embedding_hnsw "
        "ON signals USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_signals_embedding_hnsw")
    op.execute("ALTER TABLE signals ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_embedding_hnsw "
        "ON signals USING hnsw (embedding vector_cosine_ops)"
    )
