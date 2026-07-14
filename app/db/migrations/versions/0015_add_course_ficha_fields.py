"""add ficha fields to courses (credits, difficulty, course_type)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-13

⚠️ RECONSTRUCCIÓN de una migración que se aplicó a Neon "fuera de banda" (rama de
fichas, 2026-07-13) y quedó registrada como `alembic_version = 0015` SIN que su
archivo se commiteara al repo. Neon YA tiene estas columnas, así que allí esta
migración no se re-ejecuta (está en 0015); solo corre en BD nuevas (local/tests)
para que su esquema coincida con producción. Definiciones tomadas del esquema real
de Neon: `credits INTEGER NOT NULL DEFAULT 0`, `difficulty INTEGER NULL`,
`course_type VARCHAR(20) NULL`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("credits", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("courses", sa.Column("difficulty", sa.Integer(), nullable=True))
    op.add_column("courses", sa.Column("course_type", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("courses", "course_type")
    op.drop_column("courses", "difficulty")
    op.drop_column("courses", "credits")
