from app.domains.chat.store import Conversation, ConversationStore
from app.integrations.agent.ulima_agent import UlimaAgentClient


class ConversationNotFoundError(Exception):
    """La conversación solicitada no existe en el store."""


def _derive_title(message: str, limit: int = 60) -> str:
    title = " ".join(message.strip().split())
    return title[: limit - 1] + "…" if len(title) > limit else title


class ChatService:
    """Orquesta el store de conversaciones in-memory y el agente in-process."""

    def __init__(self, agent: UlimaAgentClient, store: ConversationStore) -> None:
        self._agent = agent
        self._store = store

    async def create_conversation(
        self, title: str | None = None, mode: str | None = None
    ) -> Conversation:
        conversation = self._store.create(title=title, mode=mode)
        # Liga una sesión ADK (in-memory) a la conversación para mantener contexto.
        conversation.adk_session_id = await self._agent.create_session()
        return conversation

    def list_conversations(self) -> list[Conversation]:
        return self._store.list()

    def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = self._store.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def delete_conversation(self, conversation_id: str) -> None:
        if not self._store.delete(conversation_id):
            raise ConversationNotFoundError(conversation_id)

    async def send_message(self, conversation_id: str, message: str) -> str:
        conversation = self.get_conversation(conversation_id)

        # Sesión perezosa por si la conversación se creó sin una (robustez).
        if not conversation.adk_session_id:
            conversation.adk_session_id = await self._agent.create_session()

        is_first_message = not conversation.messages
        self._store.add_message(conversation_id, "user", message)
        if is_first_message and conversation.title == "Nueva conversación":
            conversation.title = _derive_title(message)

        reply = await self._agent.ask(message, session_id=conversation.adk_session_id)
        self._store.add_message(conversation_id, "assistant", reply)
        return reply
