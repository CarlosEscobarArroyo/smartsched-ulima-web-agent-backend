"""Dependencies de autenticación: usuario actual y control de rol (US-24)."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.domains.users import repository
from app.domains.users.models import User, UserRole

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Valida el JWT del header `Authorization: Bearer` y devuelve el usuario."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise unauthorized

    user = await repository.get_by_id(db, payload["sub"])
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(role: UserRole) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Factory de dependency que exige un rol específico (p. ej. admin)."""

    async def _checker(current: Annotated[User, Depends(get_current_user)]) -> User:
        if current.role != role.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para esta acción",
            )
        return current

    return _checker
