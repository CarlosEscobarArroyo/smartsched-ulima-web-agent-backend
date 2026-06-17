"""create reviews table (US-21)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-15

Reseñas de estudiantes sobre profesores.
Una reseña por usuario por profesor (UNIQUE professor_id + user_id).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "professor_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("professors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("professor_id", "user_id", name="uq_review_professor_user"),
    )


def downgrade() -> None:
    op.drop_table("reviews")
