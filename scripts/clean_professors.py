"""Limpieza idempotente de datos de profesores y reseñas (calidad de datos).

Motivo: la tabla `professors` acumuló filas de prueba y duplicados que ensucian
las respuestas del agente IA (tools de US-15/16/17/18). Este script:

  1. Borra reseñas basura (comentario vacío / solo espacios).
  2. Borra el profesor de prueba obvio ("ASDASDA").
  3. Deduplica profesores con el mismo nombre, conservando UNA fila por nombre.
     Se conserva la fila con más reseñas (y, a igualdad, la más antigua por id);
     las demás se eliminan. Antes de borrar, reasigna cualquier reseña de las
     filas duplicadas a la fila que se conserva, para no perder reseñas.

NO toca "DR. CESAR LOLI CHAU": parece un docente real sin metadata; si quieres
eliminarlo, pásalo por --extra-junk o hazlo a mano.

Es idempotente: correrlo de nuevo no cambia nada una vez limpio.

Uso:
    uv run python scripts/clean_professors.py            # aplica los cambios
    uv run python scripts/clean_professors.py --dry-run  # solo muestra qué haría
"""

import argparse
import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


async def _rows(db, sql, **params):
    res = await db.execute(text(sql), params)
    cols = list(res.keys())
    return [dict(zip(cols, r, strict=False)) for r in res.fetchall()]


async def main(dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        # 1) Reseñas basura (comentario vacío).
        basura = await _rows(
            db,
            "SELECT r.id::text AS id, p.name FROM reviews r "
            "JOIN professors p ON p.id=r.professor_id "
            "WHERE btrim(coalesce(r.comment,'')) = ''",
        )
        print(f"Reseñas basura (comentario vacío): {len(basura)}")
        for r in basura:
            print(f"  - {r['name']}  ({r['id']})")
        if basura and not dry_run:
            await db.execute(text("DELETE FROM reviews WHERE btrim(coalesce(comment,'')) = ''"))

        # 2) Profesor de prueba obvio.
        asd = await _rows(db, "SELECT id::text AS id, name FROM professors WHERE name = 'ASDASDA'")
        print(f"\nProfesores de prueba a borrar: {len(asd)}")
        for r in asd:
            print(f"  - {r['name']}  ({r['id']})")
        if asd and not dry_run:
            # Borra primero sus reseñas (por si quedara alguna) y luego el profesor.
            await db.execute(
                text("DELETE FROM reviews WHERE professor_id IN "
                     "(SELECT id FROM professors WHERE name = 'ASDASDA')")
            )
            await db.execute(text("DELETE FROM professors WHERE name = 'ASDASDA'"))

        # 3) Duplicados por nombre.
        grupos = await _rows(
            db,
            "SELECT lower(name) AS clave, count(*) AS n FROM professors "
            "GROUP BY lower(name) HAVING count(*) > 1 ORDER BY lower(name)",
        )
        print(f"\nNombres duplicados: {len(grupos)}")
        total_borrar = 0
        for g in grupos:
            filas = await _rows(
                db,
                "SELECT p.id::text AS id, p.name, "
                "(SELECT count(*) FROM reviews r WHERE r.professor_id=p.id) AS nrev "
                "FROM professors p WHERE lower(p.name)=:clave ORDER BY nrev DESC, id ASC",
                clave=g["clave"],
            )
            conservar = filas[0]
            borrar = filas[1:]
            total_borrar += len(borrar)
            print(f"  {conservar['name']}: conservar {conservar['id']} "
                  f"(reseñas={conservar['nrev']}), borrar {[f['id'] for f in borrar]}")
            if not dry_run:
                for f in borrar:
                    # Reasigna reseñas del duplicado a la fila que se conserva (evita perderlas).
                    await db.execute(
                        text("UPDATE reviews SET professor_id=:keep WHERE professor_id=:drop"),
                        {"keep": conservar["id"], "drop": f["id"]},
                    )
                    await db.execute(
                        text("DELETE FROM professors WHERE id=:drop"), {"drop": f["id"]}
                    )
        print(f"  -> filas duplicadas a borrar: {total_borrar}")

        if dry_run:
            print("\n[DRY-RUN] No se aplicó ningún cambio.")
            return
        await db.commit()

        total = (await _rows(db, "SELECT count(*) AS n FROM professors"))[0]["n"]
        nrev = (await _rows(db, "SELECT count(*) AS n FROM reviews"))[0]["n"]
        print(f"\nLimpieza aplicada. professors={total}, reviews={nrev}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="solo muestra qué haría")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
