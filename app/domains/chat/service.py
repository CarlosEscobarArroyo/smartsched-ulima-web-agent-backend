import uuid

from app.domains.chat.schemas import ChatRequest, ChatResponse
from app.integrations.agent.ulima_agent import UlimaAgentClient


class ChatService:
    def __init__(self, agent: UlimaAgentClient) -> None:
        self._agent = agent

    async def handle(self, payload: ChatRequest) -> ChatResponse:
        session_id = payload.session_id or str(uuid.uuid4())
        reply = await self._agent.ask(payload.message, session_id=session_id)
        return ChatResponse(reply=reply, session_id=session_id)
