from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.domains.users.models import Profesor

# ---------------------------------------------------------------------------
# Modelos de dominio (dataclasses) usados por el generador (US-07).
# ---------------------------------------------------------------------------


@dataclass
class Horario:
    dia: str  # "LUN" | "MAR" | "MIE" | "JUE" | "VIE" | "SAB"
    inicio: str  # "08:00"
    fin: str  # "10:00"


@dataclass
class Seccion:
    nombre: str  # "A", "B", "01", etc.
    profe: Profesor
    horarios: list[Horario] = field(default_factory=list)


@dataclass
class Curso:
    codigo: str
    nombre: str
    creditos: int
    ciclo: str  # "2026-0" | "2026-1" | "2026-2"
    secciones: list[Seccion] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Modelo ORM: horario guardado por el usuario (US-09).
# ---------------------------------------------------------------------------


class SavedSchedule(Base):
    """Horario que el estudiante guarda desde "Horarios Generados" (máx. 10)."""

    __tablename__ = "saved_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Snapshot de la opción elegida. JSONB en Postgres, JSON en SQLite (tests).
    schedule_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
