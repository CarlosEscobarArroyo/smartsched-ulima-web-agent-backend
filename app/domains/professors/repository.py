"""Acceso a datos de profesores y reseñas para endpoints públicos (US-21)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import Course, Professor, Review
from app.domains.users.models import User


async def list_professors(db: AsyncSession) -> list[Professor]:
    result = await db.execute(select(Professor).order_by(Professor.name))
    return list(result.scalars().all())


async def get_professor_by_id(db: AsyncSession, professor_id: str) -> Professor | None:
    result = await db.execute(select(Professor).where(Professor.id == professor_id))
    return result.scalar_one_or_none()


async def list_reviews_for_professor(db: AsyncSession, professor_id: str) -> list[tuple[Review, str]]:
    """Devuelve lista de (Review, user_name) para un profesor."""
    result = await db.execute(
        select(Review, User.name)
        .join(User, User.id == Review.user_id)
        .where(Review.professor_id == professor_id)
        .order_by(Review.created_at.desc())
    )
    return list(result.tuples().all())


async def list_courses_for_professor(db: AsyncSession, professor_id: str) -> list[Course]:
    result = await db.execute(
        select(Course).where(Course.professor_id == professor_id).order_by(Course.name)
    )
    return list(result.scalars().all())


async def list_reviews_by_user(
    db: AsyncSession, user_id: str
) -> list[tuple[Review, str, str]]:
    """Devuelve lista de (Review, professor_name, course_name) para un usuario."""
    # Subquery correlacionado: toma el primer curso del profesor de la reseña.
    course_subq = (
        select(Course.name)
        .where(Course.professor_id == Review.professor_id)
        .order_by(Course.name)
        .limit(1)
        .correlate(Review)
        .scalar_subquery()
    )
    result = await db.execute(
        select(Review, Professor.name, course_subq.label("course_name"))
        .join(Professor, Professor.id == Review.professor_id)
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
    )
    return list(result.tuples().all())


async def delete_review_by_user(
    db: AsyncSession, review_id: str, user_id: str
) -> bool:
    """Elimina la reseña si pertenece al usuario. Retorna True si se eliminó."""
    result = await db.execute(
        select(Review).where(Review.id == review_id, Review.user_id == user_id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        return False
    await db.delete(review)
    await db.commit()
    return True


async def get_review_by_user_and_professor(
    db: AsyncSession, user_id: str, professor_id: str
) -> Review | None:
    result = await db.execute(
        select(Review).where(Review.user_id == user_id, Review.professor_id == professor_id)
    )
    return result.scalar_one_or_none()


async def create_review(
    db: AsyncSession,
    *,
    professor_id: str,
    user_id: str,
    rating: int,
    comment: str,
) -> Review | None:
    """Crea la reseña. Retorna None si ya existe una del mismo usuario para ese profesor."""
    review = Review(
        id=str(uuid.uuid4()),
        professor_id=professor_id,
        user_id=user_id,
        rating=rating,
        comment=comment,
        created_at=datetime.now(UTC),
    )
    db.add(review)
    try:
        await db.commit()
        await db.refresh(review)
        return review
    except IntegrityError:
        await db.rollback()
        return None
