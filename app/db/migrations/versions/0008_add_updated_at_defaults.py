"""add server DEFAULT now() to updated_at columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-01

Migration 0007 added updated_at as nullable, backfilled from created_at, then
set NOT NULL — but never set the DEFAULT clause. New INSERTs therefore violate
the NOT NULL constraint. This migration adds DEFAULT now() to both tables.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE professors ALTER COLUMN updated_at SET DEFAULT now()")
    op.execute("ALTER TABLE courses ALTER COLUMN updated_at SET DEFAULT now()")


def downgrade() -> None:
    op.execute("ALTER TABLE professors ALTER COLUMN updated_at DROP DEFAULT")
    op.execute("ALTER TABLE courses ALTER COLUMN updated_at DROP DEFAULT")
