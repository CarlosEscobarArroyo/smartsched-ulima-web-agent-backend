from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.url import build_engine_url

settings = get_settings()

# Normaliza la URL (quita params estilo libpq) y activa SSL en hosts remotos (Neon).
_engine_url, _connect_args = build_engine_url(settings.database_url)

# Singleton (creacional): el engine y el sessionmaker se crean UNA sola vez al
# importar el módulo y se comparten en todo el proceso. `get_db()` abre una sesión
# efímera por request desde este pool compartido.
engine = create_async_engine(
    _engine_url,
    echo=settings.debug,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
