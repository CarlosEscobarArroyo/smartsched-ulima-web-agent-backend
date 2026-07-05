"""add department, degree, bio, email to professors

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("professors", sa.Column("department", sa.String(120), nullable=True))
    op.add_column("professors", sa.Column("degree", sa.String(200), nullable=True))
    op.add_column("professors", sa.Column("bio", sa.String(1000), nullable=True))
    op.add_column("professors", sa.Column("email", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("professors", "email")
    op.drop_column("professors", "bio")
    op.drop_column("professors", "degree")
    op.drop_column("professors", "department")
