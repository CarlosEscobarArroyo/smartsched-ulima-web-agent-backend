from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import time

Day = int


def _to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


@dataclass(frozen=True)
class TimeBlock:
    day: Day
    start: time
    end: time

    def __post_init__(self) -> None:
        if _to_minutes(self.start) >= _to_minutes(self.end):
            raise ValueError(f"start>=end en bloque {self}")
        if not 0 <= self.day <= 6:
            raise ValueError(f"day fuera de rango: {self.day}")

    def overlaps(self, other: TimeBlock) -> bool:
        if self.day != other.day:
            return False
        return _to_minutes(self.start) < _to_minutes(other.end) and \
               _to_minutes(other.start) < _to_minutes(self.end)


@dataclass(frozen=True)
class ClassSection:
    name: str
    section_id: str
    blocks: tuple[TimeBlock, ...]

    def overlaps(self, other: ClassSection) -> bool:
        return any(a.overlaps(b) for a in self.blocks for b in other.blocks)

    def overlaps_any(self, blocks: Iterable[TimeBlock]) -> bool:
        return any(a.overlaps(b) for a in self.blocks for b in blocks)


def generate_schedules(
    sections: list[ClassSection],
    unavailable: list[TimeBlock],
    target: int,
) -> Iterator[tuple[ClassSection, ...]]:
    """Itera todas las combinaciones de `target` secciones sin conflictos.

    Reglas:
      - No puede haber dos secciones con el mismo `name` en el horario.
      - Ninguna sección puede solaparse con bloques de `unavailable`.
      - Las secciones entre sí no pueden solaparse.
    """
    if target <= 0:
        raise ValueError("target debe ser un entero positivo")

    candidates = [s for s in sections if not s.overlaps_any(unavailable)]
    by_name: dict[str, list[ClassSection]] = {}
    for s in candidates:
        by_name.setdefault(s.name, []).append(s)

    # Si el número de materias únicas disponibles es menor que el objetivo,
    # es imposible generar un horario.
    if len(by_name) < target:
        return

    names = list(by_name.keys())

    def backtrack(
        idx: int, chosen: list[ClassSection]
    ) -> Iterator[tuple[ClassSection, ...]]:
        if len(chosen) == target:
            yield tuple(chosen)
            return
        remaining_names = len(names) - idx
        if remaining_names < target - len(chosen):
            return
        for i in range(idx, len(names)):
            for section in by_name[names[i]]:
                if any(section.overlaps(c) for c in chosen):
                    continue
                chosen.append(section)
                yield from backtrack(i + 1, chosen)
                chosen.pop()

    yield from backtrack(0, [])


def parse_time(s: str) -> time:
    try:
        h, m = str(s).split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Formato de hora inválido: {s!r}") from exc


def section_from_dict(d: dict) -> ClassSection:
    blocks = tuple(
        TimeBlock(day=int(b["day"]), start=parse_time(b["start"]), end=parse_time(b["end"]))
        for b in d["blocks"]
    )
    return ClassSection(name=d["name"], section_id=d["section_id"], blocks=blocks)


def block_from_dict(d: dict) -> TimeBlock:
    return TimeBlock(day=int(d["day"]), start=parse_time(d["start"]), end=parse_time(d["end"]))


def schedule_to_dict(schedule: tuple[ClassSection, ...]) -> list[dict]:
    return [
        {
            "name": s.name,
            "section_id": s.section_id,
            "blocks": [
                {"day": b.day, "start": b.start.strftime("%H:%M"), "end": b.end.strftime("%H:%M")}
                for b in s.blocks
            ],
        }
        for s in schedule
    ]


DAY_MAP = {"LUN": 0, "MAR": 1, "MIE": 2, "JUE": 3, "VIE": 4, "SAB": 5, "DOM": 6}


def parse_ocr_to_sections(ocr_data: dict) -> list[ClassSection]:
    """Convierte el JSON del OCR a una lista plana de ClassSection."""
    all_sections = []
    for curso in ocr_data.get("cursos", []):
        course_name = curso.get("nombre", "N/A")
        for seccion in curso.get("secciones", []):
            blocks = []
            for horario_item in seccion.get("horario", []):
                day_str = horario_item.get("dia")
                inicio = horario_item.get("inicio")
                fin = horario_item.get("fin")
                if day_str not in DAY_MAP or not inicio or not fin:
                    continue

                day = DAY_MAP[day_str]
                try:
                    start = parse_time(inicio)
                    end = parse_time(fin)
                except ValueError:
                    continue
                blocks.append(TimeBlock(day=day, start=start, end=end))

            if not blocks:
                continue

            all_sections.append(
                ClassSection(
                    name=course_name,
                    section_id=seccion.get("seccion", "N/A"),
                    blocks=tuple(blocks),
                )
            )
    return all_sections