"""add professor_id to courses

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31

Asocia cursos con su docente (professor_id FK nullable).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("professor_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_courses_professor_id", "courses", "professors",
        ["professor_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_courses_professor_id", "courses", ["professor_id"])


def downgrade() -> None:
    op.drop_index("ix_courses_professor_id", table_name="courses")
    op.drop_constraint("fk_courses_professor_id", "courses", type_="foreignkey")
    op.drop_column("courses", "professor_id")
