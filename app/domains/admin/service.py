"""Lógica del panel de administración (US-29/30/31/32)."""

import csv
import io
import re

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domains.admin import repository as admin_repo
from app.domains.admin.schemas import (
    AdminCourseOut,
    AdminProfessorOut,
    AdminStatsOut,
    AdminUserOut,
    BulkDeleteProfessorsRequest,
    BulkDeleteProfessorsResult,
    CreateAdminCourseRequest,
    CreateAdminProfessorRequest,
    CreateAdminUserRequest,
    ImportProfessorsResult,
    UpdateAdminCourseRequest,
    UpdateAdminProfessorRequest,
    UpdateAdminUserRequest,
)
from app.domains.users import repository
from app.domains.users.models import User, UserRole


def _to_out(user: User) -> AdminUserOut:
    return AdminUserOut.model_validate(user)


async def list_users(db: AsyncSession) -> list[AdminUserOut]:
    users = await repository.list_all(db)
    return [_to_out(u) for u in users]


async def create_user(db: AsyncSession, payload: CreateAdminUserRequest) -> AdminUserOut:
    existing = await repository.get_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )
    user = await repository.create(
        db,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    return _to_out(user)


async def update_user(
    db: AsyncSession, user_id: str, payload: UpdateAdminUserRequest
) -> AdminUserOut:
    existing = await repository.get_by_email(db, payload.email)
    if existing is not None and existing.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo",
        )
    user = await repository.update_by_id(
        db, user_id, name=payload.name, email=payload.email, role=payload.role
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return _to_out(user)


async def delete_user(db: AsyncSession, admin_id: str, user_id: str) -> None:
    if admin_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puede eliminar su propia cuenta",
        )
    found = await repository.delete_by_id(db, user_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")


async def get_stats(db: AsyncSession) -> AdminStatsOut:
    total = await repository.count_all(db)
    students = await repository.count_by_role(db, UserRole.STUDENT.value)
    admins = await repository.count_by_role(db, UserRole.ADMIN.value)
    professors = await admin_repo.count_professors(db)
    courses = await admin_repo.count_courses(db)
    return AdminStatsOut(
        total_users=total,
        student_count=students,
        admin_count=admins,
        professor_count=professors,
        course_count=courses,
    )


# ---------------------------------------------------------------------------
# Profesores
# ---------------------------------------------------------------------------


def _professor_initials(name: str) -> str:
    cleaned = re.sub(r"(?i)^(?:dr\.?|dra\.?|prof\.?|mg\.?)\s*", "", name)
    parts = cleaned.strip().split()
    first = parts[0][0] if parts else ""
    second = (
        parts[1][0]
        if len(parts) > 1
        else (parts[0][1] if parts and len(parts[0]) > 1 else "")
    )
    return (first + second).upper()


def _prof_to_out(p: object) -> AdminProfessorOut:
    return AdminProfessorOut(
        id=p.id,
        name=p.name,
        initials=_professor_initials(p.name),
        department=p.department,
        degree=p.degree,
        bio=p.bio,
        email=p.email,
        review_count=0,
        updated_at=p.updated_at,
    )


async def list_professors(db: AsyncSession) -> list[AdminProfessorOut]:
    profs = await admin_repo.list_professors(db)
    return [_prof_to_out(p) for p in profs]


async def create_professor(
    db: AsyncSession, payload: CreateAdminProfessorRequest
) -> AdminProfessorOut:
    p = await admin_repo.create_professor(
        db,
        name=payload.name,
        department=payload.department,
        degree=payload.degree,
        bio=payload.bio,
        email=payload.email,
    )
    return _prof_to_out(p)


async def update_professor(
    db: AsyncSession, professor_id: str, payload: UpdateAdminProfessorRequest
) -> AdminProfessorOut:
    p = await admin_repo.update_professor(
        db,
        professor_id,
        name=payload.name,
        department=payload.department,
        degree=payload.degree,
        bio=payload.bio,
        email=payload.email,
    )
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado"
        )
    return _prof_to_out(p)


async def delete_professor(db: AsyncSession, professor_id: str) -> None:
    found = await admin_repo.delete_professor(db, professor_id)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado"
        )


async def bulk_delete_professors(
    db: AsyncSession, ids: list[str]
) -> BulkDeleteProfessorsResult:
    deleted, not_found = await admin_repo.bulk_delete_professors(db, ids)
    return BulkDeleteProfessorsResult(deleted=deleted, not_found=not_found)


async def import_professors_csv(db: AsyncSession, content: bytes) -> ImportProfessorsResult:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo CSV")

    reader = csv.DictReader(io.StringIO(text))
    created = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=1):
        name = (row.get("nombre") or row.get("name") or "").strip()
        if not name or len(name) < 2:
            errors.append(f"Fila {row_num}: nombre inválido o vacío")
            continue
        if len(name) > 120:
            errors.append(f"Fila {row_num}: nombre demasiado largo (máx. 120 caracteres)")
            continue

        department = (row.get("departamento") or row.get("department") or "").strip() or None
        degree = (row.get("grado") or row.get("degree") or "").strip() or None
        bio = (row.get("bio") or "").strip() or None
        email = (row.get("email") or "").strip() or None

        try:
            await admin_repo.create_professor(
                db, name=name, department=department, degree=degree, bio=bio, email=email
            )
            created += 1
        except Exception as exc:
            errors.append(f"Fila {row_num}: error al crear profesor ({exc})")

    return ImportProfessorsResult(created=created, errors=errors)


# ---------------------------------------------------------------------------
# Cursos
# ---------------------------------------------------------------------------


async def _get_professor_name(db: AsyncSession, professor_id: str | None) -> str | None:
    if professor_id is None:
        return None
    prof = await admin_repo.get_professor_by_id(db, professor_id)
    return prof.name if prof else None


async def list_courses(db: AsyncSession) -> list[AdminCourseOut]:
    courses = await admin_repo.list_courses(db)
    result = []
    for c in courses:
        result.append(
            AdminCourseOut(
                id=c.id,
                code=c.code,
                name=c.name,
                level=c.level,
                prerequisites=c.prerequisites or [],
                professor_id=c.professor_id,
                professor_name=await _get_professor_name(db, c.professor_id),
                updated_at=c.updated_at,
            )
        )
    return result


async def create_course(db: AsyncSession, payload: CreateAdminCourseRequest) -> AdminCourseOut:
    existing = await admin_repo.get_course_by_code(db, payload.code.upper())
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un curso con ese código",
        )
    c = await admin_repo.create_course(
        db,
        code=payload.code.upper(),
        name=payload.name,
        level=payload.level,
        prerequisites=payload.prerequisites,
        professor_id=payload.professor_id,
    )
    return AdminCourseOut(
        id=c.id,
        code=c.code,
        name=c.name,
        level=c.level,
        prerequisites=c.prerequisites or [],
        professor_id=c.professor_id,
        professor_name=await _get_professor_name(db, c.professor_id),
        updated_at=c.updated_at,
    )


async def update_course(
    db: AsyncSession, course_id: str, payload: UpdateAdminCourseRequest
) -> AdminCourseOut:
    existing = await admin_repo.get_course_by_code(db, payload.code.upper())
    if existing is not None and existing.id != course_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un curso con ese código",
        )
    c = await admin_repo.update_course(
        db,
        course_id,
        code=payload.code.upper(),
        name=payload.name,
        level=payload.level,
        prerequisites=payload.prerequisites,
        professor_id=payload.professor_id,
    )
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")
    return AdminCourseOut(
        id=c.id,
        code=c.code,
        name=c.name,
        level=c.level,
        prerequisites=c.prerequisites or [],
        professor_id=c.professor_id,
        professor_name=await _get_professor_name(db, c.professor_id),
        updated_at=c.updated_at,
    )


async def delete_course(db: AsyncSession, course_id: str) -> None:
    found = await admin_repo.delete_course(db, course_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")
