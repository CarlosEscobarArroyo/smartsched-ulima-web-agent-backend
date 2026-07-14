"""add photo_gcs_path to professors

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-14

Añade a `professors` la ruta gs:// de su foto (US-15 / ficha visual): la imagen
vive en GCS y aquí se guarda solo su ruta. Nullable: un profesor sin foto tiene
este campo en NULL y la ficha usa un monograma con sus iniciales.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("professors", sa.Column("photo_gcs_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("professors", "photo_gcs_path")
