"""Seed idempotente de profesores y cursos demo (US-21/US-32).

Uso: uv run python scripts/seed_professors.py
"""

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.domains.admin.models import Course, Professor

PROFESSORS = [
    {"id": "10000000-0000-0000-0000-000000000001", "name": "DR. GARCIA LOPEZ MIGUEL"},
    {"id": "10000000-0000-0000-0000-000000000002", "name": "DRA. MARTINEZ SILVA ROSA"},
    {"id": "10000000-0000-0000-0000-000000000003", "name": "MG. TORRES QUISPE JOSE"},
    {"id": "10000000-0000-0000-0000-000000000004", "name": "ING. VILLANUEVA CASTRO DIANA"},
    {"id": "10000000-0000-0000-0000-000000000005", "name": "DR. ROJAS MENDOZA CARLOS"},
]

COURSES = [
    {
        "id": "20000000-0000-0000-0000-000000000001",
        "code": "CS101",
        "name": "PROGRAMACION I",
        "level": "1",
        "prerequisites": [],
        "professor_id": "10000000-0000-0000-0000-000000000001",
    },
    {
        "id": "20000000-0000-0000-0000-000000000002",
        "code": "CS201",
        "name": "PROGRAMACION II",
        "level": "2",
        "prerequisites": ["CS101"],
        "professor_id": "10000000-0000-0000-0000-000000000001",
    },
    {
        "id": "20000000-0000-0000-0000-000000000003",
        "code": "MAT101",
        "name": "CALCULO I",
        "level": "1",
        "prerequisites": [],
        "professor_id": "10000000-0000-0000-0000-000000000002",
    },
    {
        "id": "20000000-0000-0000-0000-000000000004",
        "code": "MAT201",
        "name": "CALCULO II",
        "level": "2",
        "prerequisites": ["MAT101"],
        "professor_id": "10000000-0000-0000-0000-000000000002",
    },
    {
        "id": "20000000-0000-0000-0000-000000000005",
        "code": "CS301",
        "name": "ESTRUCTURA DE DATOS",
        "level": "3",
        "prerequisites": ["CS201"],
        "professor_id": "10000000-0000-0000-0000-000000000003",
    },
    {
        "id": "20000000-0000-0000-0000-000000000006",
        "code": "CS401",
        "name": "BASE DE DATOS",
        "level": "4",
        "prerequisites": ["CS301"],
        "professor_id": "10000000-0000-0000-0000-000000000004",
    },
    {
        "id": "20000000-0000-0000-0000-000000000007",
        "code": "CS501",
        "name": "INGENIERIA DE SOFTWARE I",
        "level": "5",
        "prerequisites": ["CS301"],
        "professor_id": "10000000-0000-0000-0000-000000000005",
    },
    {
        "id": "20000000-0000-0000-0000-000000000008",
        "code": "CS502",
        "name": "INGENIERIA DE SOFTWARE II",
        "level": "5",
        "prerequisites": ["CS501"],
        "professor_id": "10000000-0000-0000-0000-000000000005",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for data in PROFESSORS:
            existing = await db.scalar(select(Professor).where(Professor.id == data["id"]))
            if existing is not None:
                print(f"= ya existe profesor: {data['name']}")
                continue
            db.add(Professor(id=data["id"], name=data["name"]))
            print(f"+ creado profesor: {data['name']}")

        await db.flush()  # persiste profesores en la transacción antes de insertar cursos (FK)

        for data in COURSES:
            existing = await db.scalar(select(Course).where(Course.id == data["id"]))
            if existing is not None:
                print(f"= ya existe curso: {data['code']}")
                continue
            db.add(
                Course(
                    id=data["id"],
                    code=data["code"],
                    name=data["name"],
                    level=data["level"],
                    prerequisites=data["prerequisites"],
                    professor_id=data["professor_id"],
                )
            )
            print(f"+ creado curso: {data['code']} - {data['name']}")

        await db.commit()
    print("Seed completado.")


if __name__ == "__main__":
    asyncio.run(main())
