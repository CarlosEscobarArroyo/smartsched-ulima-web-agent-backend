"""Acceso a datos de profesores y cursos (US-32)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import Course, Professor, Review


async def list_professors(db: AsyncSession, *, skip: int = 0, limit: int = 200) -> list[Professor]:
    result = await db.execute(
        select(Professor).order_by(Professor.created_at).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_professor_by_id(db: AsyncSession, professor_id: str) -> Professor | None:
    result = await db.execute(select(Professor).where(Professor.id == professor_id))
    return result.scalar_one_or_none()


async def create_professor(
    db: AsyncSession,
    *,
    name: str,
    department: str | None = None,
    degree: str | None = None,
    bio: str | None = None,
    email: str | None = None,
) -> Professor:
    professor = Professor(
        id=str(uuid.uuid4()),
        name=name,
        department=department,
        degree=degree,
        bio=bio,
        email=email,
    )
    db.add(professor)
    await db.commit()
    await db.refresh(professor)
    return professor


async def update_professor(
    db: AsyncSession,
    professor_id: str,
    *,
    name: str,
    department: str | None = None,
    degree: str | None = None,
    bio: str | None = None,
    email: str | None = None,
) -> Professor | None:
    professor = await get_professor_by_id(db, professor_id)
    if professor is None:
        return None
    professor.name = name
    professor.department = department
    professor.degree = degree
    professor.bio = bio
    professor.email = email
    await db.commit()
    await db.refresh(professor)
    return professor


async def delete_professor(db: AsyncSession, professor_id: str) -> bool:
    professor = await get_professor_by_id(db, professor_id)
    if professor is None:
        return False
    await db.delete(professor)
    await db.commit()
    return True


async def bulk_delete_professors(
    db: AsyncSession, professor_ids: list[str]
) -> tuple[int, list[str]]:
    deleted = 0
    not_found = []
    for pid in professor_ids:
        prof = await get_professor_by_id(db, pid)
        if prof is None:
            not_found.append(pid)
        else:
            await db.delete(prof)
            deleted += 1
    await db.commit()
    return deleted, not_found


async def count_professors(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Professor))
    return result.scalar_one()


async def count_reviews_by_professor(db: AsyncSession) -> dict[str, int]:
    """Conteo de reseñas agrupado por profesor (para el listado del panel admin)."""
    result = await db.execute(
        select(Review.professor_id, func.count()).group_by(Review.professor_id)
    )
    return {professor_id: count for professor_id, count in result.all()}


async def count_reviews_for_professor(db: AsyncSession, professor_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(Review).where(Review.professor_id == professor_id)
    )
    return result.scalar_one()


async def list_courses(db: AsyncSession, *, skip: int = 0, limit: int = 200) -> list[Course]:
    result = await db.execute(
        select(Course).order_by(Course.created_at).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_course_by_id(db: AsyncSession, course_id: str) -> Course | None:
    result = await db.execute(select(Course).where(Course.id == course_id))
    return result.scalar_one_or_none()


async def get_course_by_code(db: AsyncSession, code: str) -> Course | None:
    result = await db.execute(select(Course).where(Course.code == code))
    return result.scalar_one_or_none()


async def create_course(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    level: str,
    prerequisites: list[str],
    professor_id: str | None = None,
) -> Course:
    course = Course(
        id=str(uuid.uuid4()),
        code=code,
        name=name,
        level=level,
        prerequisites=prerequisites,
        professor_id=professor_id,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def update_course(
    db: AsyncSession,
    course_id: str,
    *,
    code: str,
    name: str,
    level: str,
    prerequisites: list[str],
    professor_id: str | None = None,
) -> Course | None:
    course = await get_course_by_id(db, course_id)
    if course is None:
        return None
    course.code = code
    course.name = name
    course.level = level
    course.prerequisites = prerequisites
    course.professor_id = professor_id
    await db.commit()
    await db.refresh(course)
    return course


async def delete_course(db: AsyncSession, course_id: str) -> bool:
    course = await get_course_by_id(db, course_id)
    if course is None:
        return False
    await db.delete(course)
    await db.commit()
    return True


async def set_course_syllabus(
    db: AsyncSession,
    course_id: str,
    *,
    file_name: str,
    gcs_path: str,
    uploaded_at: datetime,
) -> Course | None:
    course = await get_course_by_id(db, course_id)
    if course is None:
        return None
    course.syllabus_file_name = file_name
    course.syllabus_gcs_path = gcs_path
    course.syllabus_uploaded_at = uploaded_at
    await db.commit()
    await db.refresh(course)
    return course


async def set_professor_photo(
    db: AsyncSession, professor_id: str, *, gcs_path: str
) -> Professor | None:
    professor = await get_professor_by_id(db, professor_id)
    if professor is None:
        return None
    professor.photo_gcs_path = gcs_path
    await db.commit()
    await db.refresh(professor)
    return professor


async def count_courses(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Course))
    return result.scalar_one()
