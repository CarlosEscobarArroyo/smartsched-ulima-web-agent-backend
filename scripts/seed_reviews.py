"""Seed idempotente de reseñas de muestra para los profesores (US-15/US-21).

Los 76 profesores casi no tenían reseñas (solo 2 demo), así que la reputación
del agente IA salía vacía. Este script las puebla con reseñas FICTICIAS pero
verosímiles y en su mayoría positivas.

Cómo funciona:
  1. Crea un pool de ~15 usuarios alumno "reseñadores" (idempotente). Son cuentas
     student reales (la tabla reviews exige user_id FK), con nombres realistas.
  2. Para CADA profesor asigna 2-4 reseñas de alumnos distintos, con rating
     variado (mayormente 4-5, algún 3) y comentarios sin repetir. La asignación
     es DETERMINISTA (RNG sembrado con el id del profesor): correrlo de nuevo da
     el mismo resultado y no duplica (respeta UNIQUE(user_id, professor_id) y
     verifica existencia antes de insertar).

NO toca las reseñas reales ya existentes (usa su propio pool de usuarios).

Uso:
    uv run python scripts/seed_reviews.py            # aplica
    uv run python scripts/seed_reviews.py --dry-run  # solo cuenta, no inserta
"""

import argparse
import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.domains.admin.models import Professor, Review
from app.domains.users.models import User, UserRole

# --- Pool de alumnos reseñadores (ids deterministas, dominio de alumno ULIMA) ---
REVIEWER_NAMES = [
    "Valeria Ramos Chávez",
    "Diego Salazar Núñez",
    "Camila Torres Ríos",
    "Sebastián Flores Vega",
    "Lucía Mendoza Paredes",
    "Mateo Rojas Quispe",
    "Fernanda Castro León",
    "Joaquín Vargas Díaz",
    "Antonella Guzmán Soto",
    "Rodrigo Herrera Campos",
    "Isabella Ponce Miranda",
    "Adrián Cáceres Bravo",
    "Micaela Espinoza Cornejo",
    "Nicolás Rivera Palma",
    "Daniela Aguirre Zamora",
]

_PASSWORD = "Alumno123"  # cuentas de muestra; no relevante para el flujo del agente


def _reviewer(idx: int, name: str) -> dict:
    slug = name.lower().split()
    email = f"{slug[0]}.{slug[1]}{idx:02d}@aloe.ulima.edu.pe"
    return {
        "id": f"30000000-0000-0000-0000-{idx:012d}",
        "name": name,
        "email": email,
    }


REVIEWERS = [_reviewer(i + 1, n) for i, n in enumerate(REVIEWER_NAMES)]

# Comentarios positivos (para rating 4-5).
POSITIVOS = [
    "Explica muy claro y con ejemplos prácticos, se le entiende bastante bien.",
    "Exigente pero justo; si estudias con tiempo, el curso se lleva sin problemas.",
    "Siempre dispuesto a resolver dudas dentro y fuera de clase.",
    "Sus clases son dinámicas y motivadoras, aprendí bastante.",
    "Da buena retroalimentación en los trabajos, se nota que revisa a detalle.",
    "Domina el tema y lo transmite con pasión, muy recomendado.",
    "Las evaluaciones son coherentes con lo que se enseña en clase.",
    "Muy organizado con el sílabo y con los plazos de entrega.",
    "Aterriza la teoría con casos reales, eso ayuda a entender el porqué.",
    "Paciente al explicar; si no entiendes, lo vuelve a ver de otra forma.",
    "Fomenta la participación y el pensamiento crítico en clase.",
    "Responde los correos rápido y está pendiente del avance del grupo.",
    "Sus materiales de apoyo son claros y útiles para repasar.",
    "Hace la clase amena y conecta bien los temas entre sí.",
    "Se preocupa por que todos aprendan, no solo por avanzar el temario.",
    "Buen trato con los alumnos y muy accesible para consultas.",
    "Prepara bien cada sesión, se nota la dedicación.",
    "Aprendí mucho más de lo que esperaba, gran profesor.",
    "Explica paso a paso y refuerza los conceptos con ejercicios.",
    "Justo al calificar y transparente con los criterios de evaluación.",
    "Motiva a investigar por cuenta propia y da buenas referencias.",
    "Uno de los mejores profesores que he tenido en la carrera.",
]

# Comentarios más mixtos (para rating 3): buenos pero con algún matiz.
MIXTOS = [
    "Sabe mucho del tema; a veces avanza rápido, conviene repasar después de clase.",
    "Buen profesor en general, aunque las clases pueden ponerse teóricas.",
    "Enseña bien, pero el curso tiene bastante carga de trabajo.",
    "Domina el tema; ayudaría que diera más ejemplos en clase.",
    "Cumple con el curso; las clases mejoran cuando hay más práctica.",
    "Correcto y ordenado, aunque el ritmo puede sentirse exigente.",
]

_BASE_DATE = datetime(2026, 7, 1, tzinfo=UTC)


async def ensure_reviewers(db, dry_run: bool) -> int:
    creados = 0
    for r in REVIEWERS:
        existing = await db.scalar(select(User).where(User.id == r["id"]))
        if existing is not None:
            continue
        creados += 1
        if not dry_run:
            db.add(
                User(
                    id=r["id"],
                    email=r["email"].lower(),
                    name=r["name"],
                    password_hash=hash_password(_PASSWORD),
                    role=UserRole.STUDENT.value,
                )
            )
    if not dry_run:
        await db.flush()  # persiste usuarios antes de insertar reseñas (FK)
    return creados


async def seed_reviews_for(db, professor: Professor, dry_run: bool) -> int:
    rng = random.Random(professor.id)  # determinista por profesor
    n = rng.choice([2, 3, 3, 4, 4])
    elegidos = rng.sample(REVIEWERS, n)
    usados: set[str] = set()
    insertadas = 0

    for reviewer in elegidos:
        # ¿Ya existe una reseña de este alumno para este profesor? -> idempotente.
        ya = await db.scalar(
            select(Review).where(
                Review.professor_id == professor.id,
                Review.user_id == reviewer["id"],
            )
        )
        if ya is not None:
            continue

        rating = rng.choices([5, 4, 3], weights=[45, 40, 15])[0]
        pool = POSITIVOS if rating >= 4 else MIXTOS
        opciones = [c for c in pool if c not in usados] or pool
        comentario = rng.choice(opciones)
        usados.add(comentario)
        created = _BASE_DATE - timedelta(days=rng.randint(5, 210))

        insertadas += 1
        if not dry_run:
            db.add(
                Review(
                    id=str(uuid.uuid4()),
                    professor_id=professor.id,
                    user_id=reviewer["id"],
                    rating=rating,
                    comment=comentario,
                    created_at=created,
                )
            )
    return insertadas


async def main(dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        creados = await ensure_reviewers(db, dry_run)
        print(f"Usuarios reseñadores nuevos: {creados} (pool total {len(REVIEWERS)})")

        profes = list((await db.execute(select(Professor).order_by(Professor.name))).scalars())
        total = 0
        for p in profes:
            total += await seed_reviews_for(db, p, dry_run)

        if dry_run:
            print(f"[DRY-RUN] Insertaría {total} reseñas sobre {len(profes)} profesores.")
            return

        await db.commit()
        count = len((await db.execute(select(Review.id))).scalars().all())
        print(f"Reseñas insertadas: {total}. Total de reseñas en BD ahora: {count}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="no inserta, solo cuenta")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
