import uuid

from app.agents.ulima_agent import UlimaAgentClient
from app.schemas.chat import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, agent: UlimaAgentClient) -> None:
        self._agent = agent

    async def handle(self, payload: ChatRequest) -> ChatResponse:
        session_id = payload.session_id or str(uuid.uuid4())
        reply = await self._agent.ask(payload.message, session_id=session_id)
        return ChatResponse(reply=reply, session_id=session_id)
