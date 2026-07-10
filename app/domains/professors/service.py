"""Lógica de negocio de profesores y reseñas (US-21)."""

import re
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import Course, Review
from app.domains.professors import repository
from app.domains.professors.schemas import (
    CourseOut,
    CreateReviewRequest,
    MyReviewOut,
    ProfessorOut,
    ReviewOut,
)
from app.domains.users.models import User


def _initials(name: str) -> str:
    cleaned = re.sub(r"(?i)^(?:dr\.?|dra\.?|prof\.?|mg\.?|ing\.?|lic\.?)\s*", "", name)
    parts = cleaned.strip().split()
    first = parts[0][0] if parts else ""
    second = (
        parts[1][0]
        if len(parts) > 1
        else (parts[0][1] if parts and len(parts[0]) > 1 else "")
    )
    return (first + second).upper()


def _professor_out_from_rows(
    professor_id: str,
    name: str,
    availability: list[str] | None,
    review_rows: list[tuple[Review, str]],
    courses: list[Course],
) -> ProfessorOut:
    reviews_out = [
        ReviewOut(
            id=r.id,
            student=user_name,
            rating=r.rating,
            comment=r.comment,
            date=r.created_at.isoformat(),
        )
        for r, user_name in review_rows
    ]

    avg_rating = (
        round(sum(r.rating for r in reviews_out) / len(reviews_out), 1)
        if reviews_out
        else 0.0
    )

    courses_out = [CourseOut(id=c.id, code=c.code, name=c.name) for c in courses]
    course_display = courses[0].name if courses else ""

    return ProfessorOut(
        id=professor_id,
        name=name,
        course=course_display,
        initials=_initials(name),
        availability=availability or [],
        rating=avg_rating,
        reviews=reviews_out,
        courses=courses_out,
    )


async def _build_professor_out(
    db: AsyncSession, professor_id: str, name: str, availability: list[str] | None
) -> ProfessorOut:
    review_rows = await repository.list_reviews_for_professor(db, professor_id)
    courses = await repository.list_courses_for_professor(db, professor_id)
    return _professor_out_from_rows(professor_id, name, availability, review_rows, courses)


async def get_professor(db: AsyncSession, professor_id: str) -> ProfessorOut:
    prof = await repository.get_professor_by_id(db, professor_id)
    if prof is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado")
    return await _build_professor_out(db, prof.id, prof.name, prof.availability)


async def list_professors(db: AsyncSession) -> list[ProfessorOut]:
    """Lista todos los profesores. Trae reseñas y cursos en 2 consultas batch (evita N+1)."""
    profs = await repository.list_professors(db)
    professor_ids = [p.id for p in profs]

    all_review_rows = await repository.list_reviews_for_professors(db, professor_ids)
    all_courses = await repository.list_courses_for_professors(db, professor_ids)

    reviews_by_professor: dict[str, list[tuple[Review, str]]] = defaultdict(list)
    for review, user_name in all_review_rows:
        reviews_by_professor[review.professor_id].append((review, user_name))

    courses_by_professor: dict[str, list[Course]] = defaultdict(list)
    for course in all_courses:
        if course.professor_id is not None:
            courses_by_professor[course.professor_id].append(course)

    return [
        _professor_out_from_rows(
            p.id,
            p.name,
            p.availability,
            reviews_by_professor.get(p.id, []),
            courses_by_professor.get(p.id, []),
        )
        for p in profs
    ]


async def list_my_reviews(db: AsyncSession, current_user: User) -> list[MyReviewOut]:
    rows = await repository.list_reviews_by_user(db, current_user.id)
    return [
        MyReviewOut(
            id=review.id,
            professor=professor_name,
            course=course_name or "",
            rating=review.rating,
            comment=review.comment,
        )
        for review, professor_name, course_name in rows
    ]


async def delete_my_review(
    db: AsyncSession, review_id: str, current_user: User
) -> None:
    deleted = await repository.delete_review_by_user(db, review_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada")


async def add_review(
    db: AsyncSession,
    professor_id: str,
    payload: CreateReviewRequest,
    current_user: User,
) -> ReviewOut:
    prof = await repository.get_professor_by_id(db, professor_id)
    if prof is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado")

    review = await repository.create_review(
        db,
        professor_id=professor_id,
        user_id=current_user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya publicaste una reseña para este profesor",
        )

    return ReviewOut(
        id=review.id,
        student=current_user.name,
        rating=review.rating,
        comment=review.comment,
        date=review.created_at.isoformat(),
    )
