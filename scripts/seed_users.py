"""Seed idempotente de usuarios demo (US-24).

Crea las dos cuentas que el FE usaba como mock:
  - alumno@ulima.edu.pe / Alumno123  (student)
  - admin@ulima.edu.pe  / Admin1234  (admin)

Uso: uv run python scripts/seed_users.py
"""

import asyncio

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.domains.users import repository
from app.domains.users.models import User, UserRole

SEED_USERS = [
    {
        "id": "stu-001",
        "email": "alumno@ulima.edu.pe",
        "name": "Alumno Demo",
        "role": UserRole.STUDENT.value,
        "password": "Alumno123",
    },
    {
        "id": "adm-001",
        "email": "admin@ulima.edu.pe",
        "name": "Admin Demo",
        "role": UserRole.ADMIN.value,
        "password": "Admin1234",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for data in SEED_USERS:
            existing = await repository.get_by_email(db, data["email"])
            if existing is not None:
                print(f"= ya existe: {data['email']}")
                continue
            db.add(
                User(
                    id=data["id"],
                    email=data["email"].lower(),
                    name=data["name"],
                    password_hash=hash_password(data["password"]),
                    role=data["role"],
                )
            )
            print(f"+ creado: {data['email']} ({data['role']})")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
