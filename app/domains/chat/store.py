"""Almacenamiento in-memory de conversaciones del Agente IA.

Esta fase de US-12 no persiste en base de datos ni usa autenticación: las
conversaciones viven en memoria del proceso y se asocian a un usuario anónimo.
Cuando se implemente auth + persistencia (US-24 / modelos Conversation+Message),
este store se reemplaza por un repositorio sobre SQLAlchemy sin tocar el router.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

ANONYMOUS_USER_ID = "anonymous"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime = field(default_factory=_now)


@dataclass
class Conversation:
    id: str
    title: str
    user_id: str = ANONYMOUS_USER_ID
    mode: str | None = None
    adk_session_id: str | None = None
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def last_message(self) -> str | None:
        return self.messages[-1].content if self.messages else None


class ConversationStore:
    """Store en memoria. Una instancia compartida por proceso."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    def create(self, title: str | None = None, mode: str | None = None) -> Conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=(title or "Nueva conversación").strip() or "Nueva conversación",
            mode=mode,
        )
        self._conversations[conversation.id] = conversation
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        return self._conversations.get(conversation_id)

    def list(self) -> list[Conversation]:
        return sorted(
            self._conversations.values(),
            key=lambda c: c.updated_at,
            reverse=True,
        )

    def delete(self, conversation_id: str) -> bool:
        """Elimina una conversación. Devuelve True si existía."""
        return self._conversations.pop(conversation_id, None) is not None

    def add_message(self, conversation_id: str, role: str, content: str) -> Message:
        conversation = self._conversations[conversation_id]
        message = Message(role=role, content=content)
        conversation.messages.append(message)
        conversation.updated_at = message.created_at
        return message

    def clear(self) -> None:
        self._conversations.clear()


_store = ConversationStore()


def get_conversation_store() -> ConversationStore:
    return _store
