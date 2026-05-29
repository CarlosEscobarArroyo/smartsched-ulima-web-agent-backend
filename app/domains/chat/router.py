from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domains.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)
from app.domains.chat.service import ChatService, ConversationNotFoundError
from app.domains.chat.store import Conversation, ConversationStore, get_conversation_store
from app.integrations.agent.ulima_agent import UlimaAgentClient, get_ulima_agent

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(
    agent: Annotated[UlimaAgentClient, Depends(get_ulima_agent)],
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
) -> ChatService:
    return ChatService(agent=agent, store=store)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def _to_summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        mode=conversation.mode,
        last_message=conversation.last_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _to_detail(conversation: Conversation) -> ConversationDetail:
    return ConversationDetail(
        **_to_summary(conversation).model_dump(),
        messages=[
            {"role": m.role, "content": m.content, "created_at": m.created_at}
            for m in conversation.messages
        ],
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(service: ChatServiceDep) -> list[ConversationSummary]:
    return [_to_summary(c) for c in service.list_conversations()]


@router.post(
    "/conversations",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    service: ChatServiceDep,
) -> ConversationDetail:
    conversation = await service.create_conversation(title=payload.title, mode=payload.mode)
    return _to_detail(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, service: ChatServiceDep) -> ConversationDetail:
    try:
        conversation = service.get_conversation(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada"
        ) from None
    return _to_detail(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, service: ChatServiceDep) -> None:
    try:
        service.delete_conversation(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada"
        ) from None


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, service: ChatServiceDep) -> ChatResponse:
    try:
        reply = await service.send_message(payload.conversation_id, payload.message)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada"
        ) from None
    return ChatResponse(reply=reply, conversation_id=payload.conversation_id)
