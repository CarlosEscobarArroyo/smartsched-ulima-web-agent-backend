"""Lógica de autenticación: login, bloqueo y reset de contraseña (US-24/25)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domains.auth.models import PasswordResetToken
from app.domains.auth.schemas import TokenResponse, UserOut
from app.domains.users import repository
from app.domains.users.models import User
from app.integrations.email.client import send_reset_email


def _is_locked(user: User, now: datetime) -> bool:
    """True si el usuario tiene un bloqueo vigente."""
    if user.locked_until is None:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:  # SQLite puede devolver naive
        locked_until = locked_until.replace(tzinfo=UTC)
    return locked_until > now


async def authenticate(db: AsyncSession, email: str, password: str) -> TokenResponse:
    """Autentica al usuario y devuelve un token, o lanza HTTP 401/423.

    Reglas (CA-2): tras `max_login_attempts` fallos consecutivos, se bloquea la
    cuenta por `lockout_minutes`. Un login exitoso resetea el contador.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    user = await repository.get_by_email(db, email)

    # Credenciales inválidas → 401 (no revelamos si el email existe).
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Correo o contraseña incorrectos",
    )

    if user is None or not user.is_active:
        raise invalid

    if _is_locked(user, now):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada por intentos fallidos. Intente en unos minutos.",
        )

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.max_login_attempts:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_attempts = 0
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Cuenta bloqueada por intentos fallidos. Intente en 15 minutos.",
            )
        await db.commit()
        raise invalid

    # Login correcto: limpiar contador/bloqueo y emitir token.
    user.failed_attempts = 0
    user.locked_until = None
    await db.commit()

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, name=user.name, role=user.role),
    )


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Genera un token de reset y envía el email. Siempre retorna sin error (no revela si el email existe)."""
    settings = get_settings()
    user = await repository.get_by_email(db, email)
    if user is None or not user.is_active:
        return

    # Invalida tokens anteriores del mismo usuario.
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.reset_token_expire_minutes)
    db.add(PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    ))
    await db.commit()

    reset_link = f"{settings.frontend_url}/reset-password?token={token}"
    send_reset_email(user.email, reset_link)


async def update_me(db: AsyncSession, current_user: User, name: str, email: str) -> UserOut:
    """Actualiza nombre y email del usuario autenticado. 409 si el email ya pertenece a otra cuenta."""
    if email.lower() != current_user.email:
        existing = await repository.get_by_email(db, email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El correo ya está en uso por otra cuenta.",
            )
    updated = await repository.update_me_fields(db, current_user, name=name, email=email)
    return UserOut(id=updated.id, email=updated.email, name=updated.name, role=updated.role)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """Valida el token y actualiza la contraseña. Lanza 400 si el token es inválido o expiró."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > now,
        )
    )
    reset_token = result.scalar_one_or_none()

    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace es inválido o ya expiró.",
        )

    user = await repository.get_by_id(db, reset_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no encontrado.")

    user.password_hash = hash_password(new_password)
    user.failed_attempts = 0
    user.locked_until = None
    reset_token.used = True
    await db.commit()
