from dataclasses import dataclass, field

from app.domains.users.models import Profesor


@dataclass
class Horario:
    dia: str    # "LUN" | "MAR" | "MIE" | "JUE" | "VIE" | "SAB"
    inicio: str  # "08:00"
    fin: str     # "10:00"


@dataclass
class Seccion:
    nombre: str   # "A", "B", "01", etc.
    profe: Profesor
    horarios: list[Horario] = field(default_factory=list)


@dataclass
class Curso:
    codigo: str
    nombre: str
    creditos: int
    ciclo: str   # "2026-0" | "2026-1" | "2026-2"
    secciones: list[Seccion] = field(default_factory=list)
