"""create reviews table

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id           TEXT PRIMARY KEY,
            user_id      TEXT REFERENCES users(id) ON DELETE SET NULL,
            professor_id TEXT NOT NULL REFERENCES professors(id) ON DELETE CASCADE,
            content      TEXT NOT NULL,
            rating       INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reviews_professor_id ON reviews(professor_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reviews")
