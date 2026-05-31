"""Schemas de generación de horarios (US-07).

Replican el contrato del frontend (`features/schedule-generator/types.ts`): el FE envía
los cursos detectados con sus secciones y los bloques no disponibles, y espera de vuelta
un horario con una lista de opciones, cada una con la sección elegida por curso.
Ver `CONTRACTS.md` §2.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DetectedSection(BaseModel):
    """Sección candidata de un curso. `horarios` son strings tipo "MIE 11:00-13:00"."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    seccion: str
    profesor: str = ""
    aula: str | None = None
    horarios: list[str] = Field(default_factory=list)


class DetectedCourse(BaseModel):
    """Curso detectado. Solo los `selected=True` entran en la generación."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    code: str
    name: str
    schedule: str | None = None
    sections: list[DetectedSection] = Field(default_factory=list)
    selected: bool = False


class GenerateRequest(BaseModel):
    """Body de `POST /api/v1/schedules/generate`.

    `blockedSlots` son strings "Dia-Hora" (hora entera), ej. "Lun-6" = 06:00-07:00.
    """

    model_config = ConfigDict(populate_by_name=True)

    courses: list[DetectedCourse] = Field(default_factory=list)
    blocked_slots: list[str] = Field(default_factory=list, alias="blockedSlots")


class GeneratedCourse(DetectedCourse):
    """Curso dentro de una opción generada, con la sección concreta elegida."""

    model_config = ConfigDict(populate_by_name=True)

    selected_section: DetectedSection = Field(alias="selectedSection")


class GeneratedScheduleOption(BaseModel):
    id: str
    courses: list[GeneratedCourse]


class GeneratedSchedule(BaseModel):
    """Respuesta de la generación. `options` vacío = no hay combinaciones sin cruces."""

    id: str
    options: list[GeneratedScheduleOption] = Field(default_factory=list)
    truncated: bool = False


class SavedScheduleCreate(BaseModel):
    """US-09: payload para guardar un horario (la opción elegida)."""

    name: str = Field(min_length=1, max_length=120)
    schedule_data: dict[str, Any]


class SavedScheduleOut(BaseModel):
    """US-09: horario guardado tal como lo consume el FE (perfil → `schedules`).

    Versión ligera (sin el blob) para la lista de "Mis horarios".
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    saved_at: str = Field(alias="savedAt")


class SavedScheduleDetailOut(SavedScheduleOut):
    """US-09: detalle de un horario guardado, incluye el blob para re-renderizarlo.

    `scheduleData` es el snapshot de la opción elegida (`GeneratedScheduleOption`
    del FE), tal como se guardó: el FE lo vuelve a pintar en la grilla.
    """

    schedule_data: dict[str, Any] = Field(alias="scheduleData")
