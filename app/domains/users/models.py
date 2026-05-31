from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

# ---------------------------------------------------------------------------
# Modelos de dominio (dataclasses) — usados por schedules/ para tipar al docente.
# ---------------------------------------------------------------------------


@dataclass
class Usuario(ABC):
    nombre: str
    codigo: str
    carrera: str

    @property
    @abstractmethod
    def tipo(self) -> str: ...


@dataclass
class Alumno(Usuario):
    ciclo_actual: int
    creditos: int

    @property
    def tipo(self) -> str:
        return "alumno"


@dataclass
class Profesor(Usuario):

    @property
    def tipo(self) -> str:
        return "profesor"


# ---------------------------------------------------------------------------
# Modelo ORM de autenticación (US-24).
# ---------------------------------------------------------------------------


class UserRole(StrEnum):
    """Roles del sistema. Coincide con el FE (`"student" | "admin"`)."""

    STUDENT = "student"
    ADMIN = "admin"


class User(Base):
    """Usuario del sistema (estudiante o admin)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.STUDENT.value)

    # Bloqueo por intentos fallidos (CA-2: 3 intentos → 15 min)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
