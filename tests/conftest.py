"""Fixtures compartidos: DB SQLite en memoria para tests con persistencia (US-24)."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.domains.admin import models as admin_models  # noqa: F401
from app.domains.chat import models as chat_models  # noqa: F401  (registra Conversation/Message)
from app.domains.schedules import models as schedules_models  # noqa: F401
from app.domains.support import models as support_models  # noqa: F401
from app.domains.users import models  # noqa: F401  (registra User en Base.metadata)
from app.domains.users.models import User, UserRole
from app.main import app


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Sesión async sobre SQLite en memoria (una sola conexión vía StaticPool)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with session_maker() as session:
        yield session

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP async contra la app ASGI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def make_user(
    db: AsyncSession,
    *,
    email: str = "alumno@ulima.edu.pe",
    password: str = "Alumno123",
    name: str = "Alumno Demo",
    role: UserRole = UserRole.STUDENT,
    user_id: str = "00000000-0000-0000-0000-000000000001",
    is_active: bool = True,
) -> User:
    """Crea y persiste un usuario de prueba."""
    user = User(
        id=user_id,
        email=email.lower(),
        name=name,
        password_hash=hash_password(password),
        role=role.value,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    return user
