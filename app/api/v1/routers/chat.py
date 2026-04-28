from fastapi import APIRouter, Depends

from app.agents.ulima_agent import UlimaAgentClient, get_ulima_agent
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(
    agent: UlimaAgentClient = Depends(get_ulima_agent),
) -> ChatService:
    return ChatService(agent=agent)


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await service.handle(payload)
