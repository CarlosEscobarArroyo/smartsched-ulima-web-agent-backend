"""Router de horarios: generación de combinaciones (US-07) y horarios guardados (US-09)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.deps import get_current_user
from app.domains.schedules import saved_service, service
from app.domains.schedules.schemas import (
    GeneratedSchedule,
    GenerateRequest,
    SavedScheduleCreate,
    SavedScheduleDetailOut,
    SavedScheduleOut,
)
from app.domains.users.models import User

router = APIRouter(prefix="/schedules", tags=["schedules"])


# Síncrono a propósito: el backtracking es CPU-bound, FastAPI lo corre en un threadpool
# y así no bloquea el event loop durante el timeout de generación.
@router.post("/generate", response_model=GeneratedSchedule)
def generate(payload: GenerateRequest) -> GeneratedSchedule:
    try:
        return service.generate(payload)
    except service.NoCoursesSelectedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/saved", response_model=SavedScheduleOut, status_code=status.HTTP_201_CREATED)
async def save_schedule(
    payload: SavedScheduleCreate,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SavedScheduleOut:
    """US-09: guarda el horario elegido del usuario (máx. 10 → 409)."""
    return await saved_service.create_saved_schedule(db, current.id, payload)


@router.get("/saved", response_model=list[SavedScheduleOut])
async def list_saved(
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SavedScheduleOut]:
    """US-09: lista los horarios guardados del usuario autenticado."""
    return await saved_service.list_saved_schedules(db, current.id)


@router.get("/saved/{schedule_id}", response_model=SavedScheduleDetailOut)
async def get_saved(
    schedule_id: str,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SavedScheduleDetailOut:
    """US-09: detalle de un horario guardado (con el blob para re-renderizarlo)."""
    return await saved_service.get_saved_schedule(db, current.id, schedule_id)


@router.delete("/saved/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved(
    schedule_id: str,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """US-09: elimina un horario guardado del usuario (404 si no es suyo)."""
    await saved_service.delete_saved_schedule(db, current.id, schedule_id)
