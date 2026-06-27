import asyncio
import asyncpg
from app.core.config import get_settings

EXTRA_TABLES = ["conversations", "messages", "reviews"]

async def check():
    s = get_settings()
    url = str(s.database_url).replace("postgresql+asyncpg", "postgresql")
    conn = await asyncpg.connect(url)
    for table in EXTRA_TABLES:
        cols = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
            """,
            table,
        )
        print(f"\n-- {table} --")
        for c in cols:
            print(f"  {c['column_name']:30s} {c['data_type']:20s} nullable={c['is_nullable']} default={c['column_default']}")
    await conn.close()

asyncio.run(check())
