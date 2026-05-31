"""Acceso a datos de usuarios (US-24)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Busca un usuario por email (case-insensitive en el valor normalizado)."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Busca un usuario por id."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
