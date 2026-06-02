"""Router del Agente IA: conversaciones y mensajes persistidos por usuario (US-12/13/14).

Todos los endpoints exigen autenticación (`get_current_user`): las conversaciones
se filtran y validan por dueño, de modo que un usuario solo ve y elimina las suyas.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.deps import get_current_user
from app.domains.chat.models import Conversation
from app.domains.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    MessageOut,
)
from app.domains.chat.service import ChatService, ConversationNotFoundError
from app.domains.users.models import User
from app.integrations.agent.ulima_agent import UlimaAgentClient, get_ulima_agent

router = APIRouter(prefix="/chat", tags=["chat"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada"
)


def get_chat_service(
    agent: Annotated[UlimaAgentClient, Depends(get_ulima_agent)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatService:
    return ChatService(agent=agent, db=db)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


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
            MessageOut(role=m.role, content=m.content, created_at=m.created_at)
            for m in conversation.messages
        ],
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current: CurrentUser, service: ChatServiceDep
) -> list[ConversationSummary]:
    conversations = await service.list_conversations(current.id)
    return [_to_summary(c) for c in conversations]


@router.post(
    "/conversations",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    current: CurrentUser,
    service: ChatServiceDep,
) -> ConversationDetail:
    conversation = await service.create_conversation(
        current.id, title=payload.title, mode=payload.mode
    )
    return _to_detail(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, current: CurrentUser, service: ChatServiceDep
) -> ConversationDetail:
    try:
        conversation = await service.get_conversation(current.id, conversation_id)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
    return _to_detail(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str, current: CurrentUser, service: ChatServiceDep
) -> None:
    try:
        await service.delete_conversation(current.id, conversation_id)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, current: CurrentUser, service: ChatServiceDep) -> ChatResponse:
    try:
        reply = await service.send_message(current.id, payload.conversation_id, payload.message)
    except ConversationNotFoundError:
        raise _NOT_FOUND from None
    return ChatResponse(reply=reply, conversation_id=payload.conversation_id)
