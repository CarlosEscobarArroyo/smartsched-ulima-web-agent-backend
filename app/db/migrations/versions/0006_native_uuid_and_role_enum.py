"""use native UUID type for all PKs/FKs and PostgreSQL ENUM for user role

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-31

Cambia todos los id/fk VARCHAR(36) a UUID nativo y el campo role a un ENUM de Postgres.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Crear el tipo ENUM y migrar la columna role
    op.execute("CREATE TYPE user_role AS ENUM ('student', 'admin')")
    # Hay que quitar el DEFAULT string antes de cambiar el tipo (Postgres no castea defaults automáticamente)
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'student'::user_role")

    # 2. Soltar FK constraints antes de cambiar los tipos de columna
    op.drop_constraint("saved_schedules_user_id_fkey", "saved_schedules", type_="foreignkey")
    op.drop_constraint("fk_courses_professor_id", "courses", type_="foreignkey")

    # 3. Convertir todas las columnas id / fk a UUID nativo
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE UUID USING id::UUID")
    op.execute("ALTER TABLE saved_schedules ALTER COLUMN id TYPE UUID USING id::UUID")
    op.execute("ALTER TABLE saved_schedules ALTER COLUMN user_id TYPE UUID USING user_id::UUID")
    op.execute("ALTER TABLE professors ALTER COLUMN id TYPE UUID USING id::UUID")
    op.execute("ALTER TABLE courses ALTER COLUMN id TYPE UUID USING id::UUID")
    op.execute("ALTER TABLE courses ALTER COLUMN professor_id TYPE UUID USING professor_id::UUID")

    # 4. Recrear FK constraints
    op.create_foreign_key(
        "saved_schedules_user_id_fkey", "saved_schedules", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_courses_professor_id", "courses", "professors",
        ["professor_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("saved_schedules_user_id_fkey", "saved_schedules", type_="foreignkey")
    op.drop_constraint("fk_courses_professor_id", "courses", type_="foreignkey")

    op.execute("ALTER TABLE courses ALTER COLUMN professor_id TYPE VARCHAR(36) USING professor_id::TEXT")
    op.execute("ALTER TABLE courses ALTER COLUMN id TYPE VARCHAR(36) USING id::TEXT")
    op.execute("ALTER TABLE professors ALTER COLUMN id TYPE VARCHAR(36) USING id::TEXT")
    op.execute("ALTER TABLE saved_schedules ALTER COLUMN user_id TYPE VARCHAR(36) USING user_id::TEXT")
    op.execute("ALTER TABLE saved_schedules ALTER COLUMN id TYPE VARCHAR(36) USING id::TEXT")
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE VARCHAR(36) USING id::TEXT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::TEXT")
    op.execute("DROP TYPE user_role")

    op.create_foreign_key(
        None, "saved_schedules", "users", ["user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_courses_professor_id", "courses", "professors",
        ["professor_id"], ["id"], ondelete="SET NULL",
    )
