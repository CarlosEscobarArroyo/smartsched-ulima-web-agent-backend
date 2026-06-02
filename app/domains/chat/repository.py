"""Acceso a datos de conversaciones y mensajes (US-13/US-14).

Todas las consultas filtran por `user_id`: una conversación solo es visible y
manipulable por su dueño. `messages` se carga con `selectinload` para poder
construir los schemas (y `last_message`) sin lazy-load en contexto async.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.chat.models import Conversation, Message


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def create_conversation(
    db: AsyncSession,
    *,
    user_id: str,
    title: str,
    mode: str | None,
    adk_session_id: str | None = None,
) -> Conversation:
    conversation = Conversation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title,
        mode=mode,
        adk_session_id=adk_session_id,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation, attribute_names=["messages"])
    return conversation


async def list_conversations(db: AsyncSession, user_id: str) -> list[Conversation]:
    """Conversaciones del usuario, de la más recientemente actualizada a la más antigua."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession, user_id: str, conversation_id: str
) -> Conversation | None:
    """Devuelve la conversación del usuario (con sus mensajes) o None si no existe/no es suya."""
    return await db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages))
    )


async def delete_conversation(db: AsyncSession, user_id: str, conversation_id: str) -> bool:
    """Elimina una conversación del usuario. Devuelve True si existía y se borró."""
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        return False
    await db.delete(conversation)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession, conversation: Conversation, role: str, content: str
) -> Message:
    """Añade un mensaje y marca la conversación como actualizada (para el orden de la lista)."""
    now = _utcnow()
    message = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        role=role,
        content=content,
        created_at=now,
    )
    db.add(message)
    conversation.updated_at = now
    await db.commit()
    await db.refresh(message)
    return message
