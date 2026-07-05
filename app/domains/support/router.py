"""Endpoints de soporte (Configuración → Contactar soporte)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth.deps import get_current_user
from app.domains.support import service
from app.domains.support.schemas import ContactMessageOut, ContactRequest
from app.domains.users.models import User

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/contact", response_model=ContactMessageOut, status_code=status.HTTP_201_CREATED)
async def contact_support(
    payload: ContactRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContactMessageOut:
    return await service.create_contact_message(db, current_user, payload)
