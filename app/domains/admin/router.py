"""Router del panel de administración (US-29/30/31)."""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.admin import service
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
from app.domains.auth.deps import require_role
from app.domains.users.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])

AdminDep = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("/stats", response_model=AdminStatsOut)
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminStatsOut:
    return await service.get_stats(db)


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> list[AdminUserOut]:
    return await service.list_users(db)


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateAdminUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminUserOut:
    return await service.create_user(db, payload)


@router.put("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: str,
    payload: UpdateAdminUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminUserOut:
    return await service.update_user(db, user_id, payload)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: AdminDep,
) -> None:
    await service.delete_user(db, current.id, user_id)


# ─── Professors ────────────────────────────────────────────────────────────


@router.get("/professors", response_model=list[AdminProfessorOut])
async def list_professors(
    db: Annotated[AsyncSession, Depends(get_db)], _current: AdminDep
) -> list[AdminProfessorOut]:
    return await service.list_professors(db)


@router.post("/professors", response_model=AdminProfessorOut, status_code=status.HTTP_201_CREATED)
async def create_professor(
    payload: CreateAdminProfessorRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminProfessorOut:
    return await service.create_professor(db, payload)


@router.delete("/professors/bulk", response_model=BulkDeleteProfessorsResult)
async def bulk_delete_professors(
    payload: BulkDeleteProfessorsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> BulkDeleteProfessorsResult:
    return await service.bulk_delete_professors(db, payload.ids)


@router.post(
    "/professors/import-csv",
    response_model=ImportProfessorsResult,
    status_code=status.HTTP_200_OK,
)
async def import_professors_csv(
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> ImportProfessorsResult:
    content = await file.read()
    return await service.import_professors_csv(db, content)


@router.put("/professors/{professor_id}", response_model=AdminProfessorOut)
async def update_professor(
    professor_id: str,
    payload: UpdateAdminProfessorRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminProfessorOut:
    return await service.update_professor(db, professor_id, payload)


@router.delete("/professors/{professor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_professor(
    professor_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> None:
    await service.delete_professor(db, professor_id)


# ─── Courses ───────────────────────────────────────────────────────────────


@router.get("/courses", response_model=list[AdminCourseOut])
async def list_courses(
    db: Annotated[AsyncSession, Depends(get_db)], _current: AdminDep
) -> list[AdminCourseOut]:
    return await service.list_courses(db)


@router.post("/courses", response_model=AdminCourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CreateAdminCourseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminCourseOut:
    return await service.create_course(db, payload)


@router.put("/courses/{course_id}", response_model=AdminCourseOut)
async def update_course(
    course_id: str,
    payload: UpdateAdminCourseRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> AdminCourseOut:
    return await service.update_course(db, course_id, payload)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current: AdminDep,
) -> None:
    await service.delete_course(db, course_id)
