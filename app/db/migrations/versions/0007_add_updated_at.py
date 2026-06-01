"""add updated_at to professors and courses

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-31

Agrega updated_at a las tablas professors y courses para auditoría de cambios.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # professors
    op.add_column("professors", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE professors SET updated_at = created_at")
    op.alter_column("professors", "updated_at", nullable=False)

    # courses
    op.add_column("courses", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE courses SET updated_at = created_at")
    op.alter_column("courses", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("courses", "updated_at")
    op.drop_column("professors", "updated_at")
