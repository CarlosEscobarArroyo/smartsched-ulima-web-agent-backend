"""Modelos ORM del Agente IA: conversaciones y mensajes persistidos (US-13/US-14).

Reemplazan al antiguo store in-memory: ahora cada conversación pertenece a un
usuario (`user_id` FK) y sobrevive a reinicios del backend. La sesión ADK
(`adk_session_id`) sigue siendo in-memory y efímera; se recrea de forma perezosa
cuando hace falta (ver `app/integrations/agent/ulima_agent.py::ensure_session`).
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Conversation(Base):
    """Conversación del estudiante con el Agente IA (US-13)."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Sesión del runner ADK (in-memory, efímera). Puede quedar obsoleta tras un
    # reinicio: se revalida/recrea de forma perezosa al enviar un mensaje.
    adk_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    @property
    def last_message(self) -> str | None:
        """Contenido del último mensaje (requiere que `messages` esté cargado)."""
        return self.messages[-1].content if self.messages else None


class Message(Base):
    """Mensaje individual dentro de una conversación (rol usuario/asistente)."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Timestamp asignado en Python al insertar: garantiza un orden estable entre el
    # mensaje del usuario y la respuesta del agente (server_default func.now() les
    # daría el mismo instante de transacción y el orden quedaría ambiguo).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
