from typing import Annotated

from fastapi import APIRouter, Depends

from app.domains.chat.schemas import ChatRequest, ChatResponse
from app.domains.chat.service import ChatService
from app.integrations.agent.ulima_agent import UlimaAgentClient, get_ulima_agent

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(
    agent: Annotated[UlimaAgentClient, Depends(get_ulima_agent)],
) -> ChatService:
    return ChatService(agent=agent)


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    return await service.handle(payload)
