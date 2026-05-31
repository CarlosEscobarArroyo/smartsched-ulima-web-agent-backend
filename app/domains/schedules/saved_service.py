"""US-09: guardar / listar / eliminar horarios del usuario (saved_schedules)."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedules.models import SavedSchedule
from app.domains.schedules.schemas import (
    SavedScheduleCreate,
    SavedScheduleDetailOut,
    SavedScheduleOut,
)

MAX_SAVED = 10  # tope por usuario (US-09)


# Se construyen por alias (savedAt/scheduleData): es lo que el plugin de pydantic
# para mypy espera cuando el campo define `Field(alias=...)`.
def _to_out(obj: SavedSchedule) -> SavedScheduleOut:
    return SavedScheduleOut(id=obj.id, name=obj.name, savedAt=obj.created_at.isoformat())


def _to_detail(obj: SavedSchedule) -> SavedScheduleDetailOut:
    return SavedScheduleDetailOut(
        id=obj.id,
        name=obj.name,
        savedAt=obj.created_at.isoformat(),
        scheduleData=obj.schedule_data,
    )


async def create_saved_schedule(
    db: AsyncSession, user_id: str, payload: SavedScheduleCreate
) -> SavedScheduleOut:
    """Guarda un horario. Lanza 409 si el usuario ya tiene el máximo permitido."""
    count = await db.scalar(
        select(func.count()).select_from(SavedSchedule).where(SavedSchedule.user_id == user_id)
    )
    if (count or 0) >= MAX_SAVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Has alcanzado el máximo de {MAX_SAVED} horarios guardados. "
            "Elimina uno para guardar otro.",
        )

    obj = SavedSchedule(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=payload.name,
        schedule_data=payload.schedule_data,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return _to_out(obj)


async def list_saved_schedules(db: AsyncSession, user_id: str) -> list[SavedScheduleOut]:
    """Lista los horarios guardados del usuario, del más reciente al más antiguo."""
    result = await db.execute(
        select(SavedSchedule)
        .where(SavedSchedule.user_id == user_id)
        .order_by(SavedSchedule.created_at.desc())
    )
    return [_to_out(obj) for obj in result.scalars().all()]


async def get_saved_schedule(
    db: AsyncSession, user_id: str, schedule_id: str
) -> SavedScheduleDetailOut:
    """Devuelve el detalle (con el blob) de un horario del usuario. 404 si no es suyo."""
    obj = await db.scalar(
        select(SavedSchedule).where(
            SavedSchedule.id == schedule_id, SavedSchedule.user_id == user_id
        )
    )
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado"
        )
    return _to_detail(obj)


async def delete_saved_schedule(db: AsyncSession, user_id: str, schedule_id: str) -> None:
    """Elimina un horario del usuario. Lanza 404 si no existe o no le pertenece."""
    obj = await db.scalar(
        select(SavedSchedule).where(
            SavedSchedule.id == schedule_id, SavedSchedule.user_id == user_id
        )
    )
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado"
        )
    await db.delete(obj)
    await db.commit()
