"""Lógica de generación de horarios (US-07).

Adapta el contrato del frontend (strings `horarios`/`blockedSlots`) al generador puro de
`app/integrations/generator/generator.py` (`ClassSection`/`TimeBlock`, backtracking), y
reconstruye el shape que el FE espera. Añade lo que la librería no trae: límite de
combinaciones (`MAX_OPTIONS`), flag `truncated` y timeout de 2 minutos (US-07 CA-1).
"""

from __future__ import annotations

import re
import time as _time
import uuid
from datetime import time

from app.domains.schedules.schemas import (
    DetectedCourse,
    DetectedSection,
    GeneratedCourse,
    GeneratedSchedule,
    GeneratedScheduleOption,
    GenerateRequest,
)
from app.integrations.generator.generator import (
    ClassSection,
    TimeBlock,
    generate_schedules,
)

MAX_OPTIONS = 20
GENERATION_TIMEOUT_SECONDS = 120

# Días tal como los emite el FE en `horarios` ("MIE 11:00-13:00") y `blockedSlots` ("Lun-6").
# Se normaliza a mayúsculas antes de buscar, igual que el DAY_MAP del frontend.
_DAY_TO_INT = {"LUN": 0, "MAR": 1, "MIE": 2, "JUE": 3, "VIE": 4, "SAB": 5, "DOM": 6}

# Mismo regex que usa el FE en generateSchedules.ts (sin capturar el aula).
_HORARIO_RE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})")


class NoCoursesSelectedError(Exception):
    """No hay ningún curso con `selected=True` en el request."""


def _parse_horario(raw: str) -> TimeBlock | None:
    """"MIE 11:00-13:00" → TimeBlock. Devuelve None si no parsea o el rango es inválido."""
    match = _HORARIO_RE.match(raw.strip())
    if not match:
        return None
    day = _DAY_TO_INT.get(match.group(1).upper())
    if day is None:
        return None
    try:
        start = time(int(match.group(2)), int(match.group(3)))
        end = time(int(match.group(4)), int(match.group(5)))
    except ValueError:
        return None
    if start >= end:
        return None
    return TimeBlock(day=day, start=start, end=end)


def _parse_blocked_slot(raw: str) -> TimeBlock | None:
    """"Lun-6" → TimeBlock 06:00-07:00. Devuelve None si no parsea."""
    parts = raw.rsplit("-", 1)
    if len(parts) != 2:
        return None
    day = _DAY_TO_INT.get(parts[0].strip().upper())
    if day is None:
        return None
    try:
        hour = int(parts[1])
    except ValueError:
        return None
    if not 0 <= hour <= 22:
        return None
    return TimeBlock(day=day, start=time(hour, 0), end=time(hour + 1, 0))


def _build_option(
    combo: tuple[ClassSection, ...],
    course_by_id: dict[str, DetectedCourse],
    section_lookup: dict[tuple[str, str], DetectedSection],
    order: dict[str, int],
) -> GeneratedScheduleOption:
    courses: list[GeneratedCourse] = []
    for cs in combo:
        course = course_by_id[cs.name]
        section = section_lookup[(cs.name, cs.section_id)]
        courses.append(
            GeneratedCourse.model_validate({**course.model_dump(), "selectedSection": section})
        )
    # Preservar el orden en que el FE envió los cursos seleccionados.
    courses.sort(key=lambda gc: order[gc.id])
    return GeneratedScheduleOption(id=str(uuid.uuid4()), courses=courses)


def generate(payload: GenerateRequest) -> GeneratedSchedule:
    """Genera hasta `MAX_OPTIONS` horarios sin cruces a partir de los cursos seleccionados.

    Reglas (heredadas de `generate_schedules`): una sección por curso, ninguna sección
    solapada con `blockedSlots` ni con las demás secciones elegidas. Lanza
    `NoCoursesSelectedError` si no hay cursos seleccionados; devuelve `options=[]` (HTTP 200)
    si las restricciones hacen imposible cualquier combinación.
    """
    selected = [c for c in payload.courses if c.selected]
    if not selected:
        raise NoCoursesSelectedError("Debe seleccionar al menos un curso.")

    # name = course.id (único por curso) para que `generate_schedules` agrupe por curso y
    # exija exactamente uno de cada uno (target = nº de cursos seleccionados).
    sections: list[ClassSection] = []
    course_by_id: dict[str, DetectedCourse] = {}
    section_lookup: dict[tuple[str, str], DetectedSection] = {}
    for course in selected:
        course_by_id[course.id] = course
        for section in course.sections:
            blocks = [tb for tb in (_parse_horario(h) for h in section.horarios) if tb]
            if not blocks:
                continue  # sección sin horarios válidos: el FE también la descarta
            sections.append(
                ClassSection(name=course.id, section_id=section.id, blocks=tuple(blocks))
            )
            section_lookup[(course.id, section.id)] = section

    unavailable = [tb for tb in (_parse_blocked_slot(s) for s in payload.blocked_slots) if tb]
    order = {c.id: i for i, c in enumerate(selected)}
    target = len(selected)

    options: list[GeneratedScheduleOption] = []
    truncated = False
    started_at = _time.monotonic()
    for combo in generate_schedules(sections, unavailable, target):
        if len(options) >= MAX_OPTIONS:
            truncated = True  # existe al menos una combinación más allá del límite
            break
        if _time.monotonic() - started_at > GENERATION_TIMEOUT_SECONDS:
            truncated = True
            break
        options.append(_build_option(combo, course_by_id, section_lookup, order))

    return GeneratedSchedule(id=str(uuid.uuid4()), options=options, truncated=truncated)
