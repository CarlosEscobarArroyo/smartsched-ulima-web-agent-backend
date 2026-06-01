"""Router del dominio de autenticación (US-24)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.auth import service
from app.domains.auth.deps import get_current_user
from app.domains.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.domains.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Login con email + contraseña. Devuelve un token Bearer y el usuario."""
    return await service.authenticate(db, payload.email, payload.password)


@router.get("/me", response_model=UserOut)
async def me(current: Annotated[User, Depends(get_current_user)]) -> UserOut:
    """Devuelve el usuario autenticado (valida el token)."""
    return UserOut(id=current.id, email=current.email, name=current.name, role=current.role)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Envía un email con el enlace de reset. Siempre responde 200 (no revela si el email existe)."""
    await service.forgot_password(db, payload.email)
    return MessageResponse(message="Si el correo está registrado, recibirás un enlace en breve.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Valida el token y actualiza la contraseña."""
    await service.reset_password(db, payload.token, payload.new_password)
    return MessageResponse(message="Contraseña actualizada. Ya puedes iniciar sesión.")
