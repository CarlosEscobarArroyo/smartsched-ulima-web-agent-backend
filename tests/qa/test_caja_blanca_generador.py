"""PRUEBA DE CAJA BLANCA — `generate_schedules()` (algoritmo de backtracking).

Módulo bajo prueba: ``app/integrations/generator/generator.py`` → ``generate_schedules``.

------------------------------------------------------------------------------
¿Por qué caja blanca?
------------------------------------------------------------------------------
La caja blanca (o "prueba estructural") diseña los casos MIRANDO el código: se
recorren sus caminos internos (ramas, bucles, condiciones) para ejercitarlos
todos. Aquí el objetivo es cubrir cada camino independiente del algoritmo.

------------------------------------------------------------------------------
Complejidad ciclomática (McCabe) de `generate_schedules`
------------------------------------------------------------------------------
Se cuenta 1 + (número de puntos de decisión). Puntos de decisión en la función
(incluyendo su función anidada `backtrack`):

    D1  if target <= 0:                              (validación)
    D2  [s for s in sections if not s.overlaps_any] (filtro de la comprensión)
    D3  for s in candidates:                         (bucle de agrupación)
    D4  if len(by_name) < target:                    (imposible: pocas materias)
    D5  if len(chosen) == target:                    (combinación completa → yield)
    D6  if remaining_names < target - len(chosen):   (poda: no alcanzan materias)
    D7  for i in range(idx, len(names)):             (bucle de materias)
    D8  for section in by_name[names[i]]:            (bucle de secciones)
    D9  if any(section.overlaps(c) for c in chosen): (poda: solapamiento)

    Complejidad ciclomática V(G) = 1 + 9 = 10   →   10 > 4  ✔

Cada test de abajo indica, en su docstring, el/los punto(s) de decisión que
cubre. En conjunto ejercitan los 10 caminos.
"""

from datetime import time

import pytest

from app.integrations.generator.generator import (
    ClassSection,
    TimeBlock,
    generate_schedules,
)

# ---------------------------------------------------------------------------
# Helpers para construir secciones de forma legible.
# ---------------------------------------------------------------------------


def _block(day: int, start: str, end: str) -> TimeBlock:
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    return TimeBlock(day=day, start=time(sh, sm), end=time(eh, em))


def _section(name: str, section_id: str, day: int, start: str, end: str) -> ClassSection:
    return ClassSection(name=name, section_id=section_id, blocks=(_block(day, start, end),))


def _names(combos):
    """Convierte combinaciones en conjuntos de (materia, sección) para comparar."""
    return [{(s.name, s.section_id) for s in combo} for combo in combos]


# ---------------------------------------------------------------------------
# D1 — validación de `target`.
# ---------------------------------------------------------------------------


def test_target_cero_lanza_valueerror() -> None:
    """Camino D1 (target <= 0): debe lanzar ValueError antes de iterar."""
    with pytest.raises(ValueError, match="entero positivo"):
        list(generate_schedules(sections=[], unavailable=[], target=0))


def test_target_negativo_lanza_valueerror() -> None:
    """Camino D1 (target <= 0) con valor negativo: mismo ValueError."""
    with pytest.raises(ValueError):
        list(generate_schedules(sections=[_section("A", "a1", 0, "08:00", "10:00")],
                                unavailable=[], target=-3))


# ---------------------------------------------------------------------------
# D2 — el filtro de `unavailable` descarta secciones que solapan un bloqueo.
# ---------------------------------------------------------------------------


def test_bloqueo_descarta_seccion_y_deja_alternativa() -> None:
    """Camino D2: `overlaps_any(unavailable)` elimina la sección solapada,
    pero queda otra sección de la misma materia → sí hay combinación."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),  # choca con el bloqueo LUN 08-10
        _section("A", "a2", 1, "08:00", "10:00"),  # MAR: sobrevive al filtro
    ]
    bloqueo = [_block(0, "08:00", "10:00")]
    combos = list(generate_schedules(secciones, bloqueo, target=1))
    assert _names(combos) == [{("A", "a2")}]


def test_bloqueo_elimina_todas_las_secciones() -> None:
    """Camino D2 + D4: si el bloqueo descarta TODAS las secciones, `by_name`
    queda vacío y no se genera ninguna combinación."""
    secciones = [_section("A", "a1", 0, "08:00", "10:00")]
    bloqueo = [_block(0, "07:00", "11:00")]  # cubre a la única sección
    combos = list(generate_schedules(secciones, bloqueo, target=1))
    assert combos == []


# ---------------------------------------------------------------------------
# D4 — menos materias únicas que el objetivo → imposible.
# ---------------------------------------------------------------------------


def test_menos_materias_que_target_no_genera() -> None:
    """Camino D4 (len(by_name) < target): 1 materia disponible pero target=2."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),
        _section("A", "a2", 1, "08:00", "10:00"),
    ]
    combos = list(generate_schedules(secciones, unavailable=[], target=2))
    assert combos == []


# ---------------------------------------------------------------------------
# D5 — camino feliz: se arma una combinación completa (yield).
# ---------------------------------------------------------------------------


def test_combinacion_completa_de_dos_materias() -> None:
    """Camino D5 (len(chosen) == target → yield): dos materias sin choque."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),
        _section("B", "b1", 1, "08:00", "10:00"),
    ]
    combos = list(generate_schedules(secciones, unavailable=[], target=2))
    assert _names(combos) == [{("A", "a1"), ("B", "b1")}]


def test_varias_combinaciones_cuando_hay_multiples_secciones() -> None:
    """Camino D5 + D7/D8 (bucles de materias y secciones): varias opciones."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),
        _section("A", "a2", 0, "10:00", "12:00"),
        _section("B", "b1", 1, "08:00", "10:00"),
    ]
    combos = list(generate_schedules(secciones, unavailable=[], target=2))
    resultado = _names(combos)
    assert {("A", "a1"), ("B", "b1")} in resultado
    assert {("A", "a2"), ("B", "b1")} in resultado
    assert len(resultado) == 2


# ---------------------------------------------------------------------------
# D9 — poda por solapamiento entre secciones ya elegidas.
# ---------------------------------------------------------------------------


def test_solapamiento_entre_materias_descarta_esa_rama() -> None:
    """Camino D9 (`any(section.overlaps(c) ...)` → continue): las únicas
    secciones de A y B chocan en el mismo horario → 0 combinaciones."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),
        _section("B", "b1", 0, "09:00", "11:00"),  # solapa con a1
    ]
    combos = list(generate_schedules(secciones, unavailable=[], target=2))
    assert combos == []


def test_solapamiento_fuerza_seccion_alternativa() -> None:
    """Camino D9 + D5: al chocar la 1ra sección de B con A, el algoritmo prueba
    la 2da sección de B (rama alternativa) y arma la combinación válida."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),
        _section("B", "b1", 0, "09:00", "11:00"),  # choca con a1 → se descarta
        _section("B", "b2", 2, "08:00", "10:00"),  # MIE: no choca → se elige
    ]
    combos = list(generate_schedules(secciones, unavailable=[], target=2))
    assert _names(combos) == [{("A", "a1"), ("B", "b2")}]


# ---------------------------------------------------------------------------
# D6 — poda temprana: no quedan suficientes materias para completar `target`.
# ---------------------------------------------------------------------------


def test_poda_por_materias_insuficientes_para_completar() -> None:
    """Camino D6 (remaining_names < target - len(chosen)): con 3 materias y
    target=3, elegir A obliga a completar con B y C; como B y C solo tienen
    secciones que chocan con A, ninguna rama llega a 3 → la poda D6 corta y el
    resultado es vacío."""
    secciones = [
        _section("A", "a1", 0, "08:00", "10:00"),
        _section("B", "b1", 0, "08:30", "10:30"),  # choca con A
        _section("C", "c1", 0, "09:00", "11:00"),  # choca con A
    ]
    combos = list(generate_schedules(secciones, unavailable=[], target=3))
    assert combos == []
