"""add syllabus fields to courses

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-13

Añade a `courses` los campos del sílabo (US-32): el archivo (PDF/DOC/DOCX) se
almacena en GCS y aquí se guarda su nombre original, la ruta gs:// del objeto y
la fecha de subida. Todo nullable: un curso sin sílabo tiene estos campos en NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("syllabus_file_name", sa.String(length=255), nullable=True))
    op.add_column("courses", sa.Column("syllabus_gcs_path", sa.String(length=500), nullable=True))
    op.add_column(
        "courses",
        sa.Column("syllabus_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("courses", "syllabus_uploaded_at")
    op.drop_column("courses", "syllabus_gcs_path")
    op.drop_column("courses", "syllabus_file_name")
