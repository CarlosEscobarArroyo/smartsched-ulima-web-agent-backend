"""Lógica de autenticación: login con bloqueo por intentos fallidos (US-24)."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.domains.auth.schemas import TokenResponse, UserOut
from app.domains.users import repository
from app.domains.users.models import User


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
