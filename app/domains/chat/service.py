"""Orquestación del chat: persistencia en BD (US-13/US-14) + agente in-process.

Cada operación está ligada a un usuario autenticado. La conversación y sus
mensajes se persisten en Postgres; la sesión del runner ADK es in-memory y se
revalida/recrea de forma perezosa al enviar un mensaje (sobrevive a reinicios
del backend porque el historial vive en la BD).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat import repository
from app.domains.chat.models import Conversation
from app.integrations.agent.ulima_agent import UlimaAgentClient

DEFAULT_TITLE = "Nueva conversación"


class ConversationNotFoundError(Exception):
    """La conversación no existe o no pertenece al usuario."""


def _derive_title(message: str, limit: int = 60) -> str:
    title = " ".join(message.strip().split())
    return title[: limit - 1] + "…" if len(title) > limit else title


class ChatService:
    """Orquesta el repositorio de conversaciones y el agente in-process por usuario."""

    def __init__(self, agent: UlimaAgentClient, db: AsyncSession) -> None:
        self._agent = agent
        self._db = db

    async def create_conversation(
        self, user_id: str, title: str | None = None, mode: str | None = None
    ) -> Conversation:
        clean_title = (title or DEFAULT_TITLE).strip() or DEFAULT_TITLE
        return await repository.create_conversation(
            self._db, user_id=user_id, title=clean_title, mode=mode
        )

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        return await repository.list_conversations(self._db, user_id)

    async def get_conversation(self, user_id: str, conversation_id: str) -> Conversation:
        conversation = await repository.get_conversation(self._db, user_id, conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    async def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        if not await repository.delete_conversation(self._db, user_id, conversation_id):
            raise ConversationNotFoundError(conversation_id)

    async def send_message(self, user_id: str, conversation_id: str, message: str) -> str:
        conversation = await self.get_conversation(user_id, conversation_id)

        is_first_message = not conversation.messages

        # Asegura una sesión ADK válida. Si se perdió (reinicio o conversación
        # reabierta), se recrea y se rehidrata con el historial guardado para que
        # el agente recupere el contexto que el usuario ve en pantalla.
        history = [(m.role, m.content) for m in conversation.messages]
        conversation.adk_session_id = await self._agent.ensure_session(
            conversation.adk_session_id, user_id, history=history
        )
        if is_first_message and conversation.title == DEFAULT_TITLE:
            conversation.title = _derive_title(message)

        # Persiste el mensaje del usuario (commitea también los cambios anteriores).
        await repository.add_message(self._db, conversation, "user", message)

        reply = await self._agent.ask(
            message, session_id=conversation.adk_session_id, user_id=user_id
        )
        await repository.add_message(self._db, conversation, "assistant", reply)
        return reply
