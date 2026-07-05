"""Lógica del módulo de soporte: persistir el mensaje y avisar al equipo."""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.support.models import SupportMessage
from app.domains.support.schemas import ContactMessageOut, ContactRequest
from app.domains.users.models import User
from app.integrations.email.client import send_support_email


async def create_contact_message(
    db: AsyncSession, current_user: User, payload: ContactRequest
) -> ContactMessageOut:
    record = SupportMessage(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        email=payload.email,
        message=payload.message,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # smtplib es síncrono: correrlo en un thread para no bloquear el event loop.
    # Best-effort: si el correo falla, el mensaje ya quedó guardado en BD.
    await asyncio.to_thread(
        send_support_email, current_user.name, payload.email, payload.message
    )

    return ContactMessageOut.model_validate(record)
