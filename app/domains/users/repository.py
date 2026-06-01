"""Acceso a datos de usuarios (US-24, US-29/30/31)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, *, skip: int = 0, limit: int = 200) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at).offset(skip).limit(limit))
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    *,
    email: str,
    name: str,
    password_hash: str,
    role: str = "student",
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=email.lower(),
        name=name,
        password_hash=password_hash,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_by_id(
    db: AsyncSession,
    user_id: str,
    *,
    name: str,
    email: str,
    role: str,
) -> User | None:
    user = await get_by_id(db, user_id)
    if user is None:
        return None
    user.name = name
    user.email = email.lower()
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user


async def delete_by_id(db: AsyncSession, user_id: str) -> bool:
    user = await get_by_id(db, user_id)
    if user is None:
        return False
    await db.delete(user)
    await db.commit()
    return True


async def count_all(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def count_by_role(db: AsyncSession, role: str) -> int:
    result = await db.execute(select(func.count()).where(User.role == role))
    return result.scalar_one()
