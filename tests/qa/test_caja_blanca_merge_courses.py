"""PRUEBA DE CAJA BLANCA — `_merge_courses()` (deduplicación de cursos del OCR).

Módulo bajo prueba: ``app/integrations/ocr/service.py`` → ``_merge_courses``.

------------------------------------------------------------------------------
¿Por qué caja blanca?
------------------------------------------------------------------------------
La caja blanca diseña los casos MIRANDO el código para recorrer todos sus caminos.
`_merge_courses` corrige una peculiaridad del modelo Gemini: a veces emite un curso
por cada sección en lugar de agruparlas. Interesa ejercitar cada rama del agrupado:
curso nuevo, curso repetido (junta secciones), sección duplicada (se ignora) y la
elección de la clave (código, o nombre si el código viene vacío).

------------------------------------------------------------------------------
Complejidad ciclomática (McCabe)
------------------------------------------------------------------------------
Puntos de decisión:

    D1  for curso in cursos:                          (bucle de cursos)
    D2  key = (curso.codigo or curso.nombre)          (`or`: código vacío → nombre)
    D3  if existing is None:                          (curso nuevo vs. repetido)
    D4  for sec in curso.secciones:                   (bucle de secciones al mergear)
    D5  if sec.seccion not in vistas:                 (sección nueva vs. duplicada)

    Complejidad ciclomática V(G) = 1 + 5 = 6   →   6 > 4  ✔
    (verificado con `radon cc`: _merge_courses = 7; el conteo automático suma
    también la comprensión de conjunto interna. En cualquier lectura supera 4.)

Es una función pura (sin BD ni red): recibe una lista y devuelve otra.
"""

from app.integrations.ocr.schemas import OCRCurso, OCRSeccion
from app.integrations.ocr.service import _merge_courses


def _curso(codigo: str, nombre: str, *secciones: str) -> OCRCurso:
    return OCRCurso(
        codigo=codigo,
        nombre=nombre,
        secciones=[OCRSeccion(seccion=s) for s in secciones],
    )


def _secciones(curso: OCRCurso) -> list[str]:
    return [s.seccion for s in curso.secciones]


# ---------------------------------------------------------------------------
# D1 — lista vacía: el bucle no itera → resultado vacío.
# ---------------------------------------------------------------------------


def test_lista_vacia_devuelve_vacio() -> None:
    """Camino D1 con 0 iteraciones."""
    assert _merge_courses([]) == []


# ---------------------------------------------------------------------------
# D3 (True) — cursos con claves distintas: cada uno se conserva por separado.
# ---------------------------------------------------------------------------


def test_cursos_distintos_se_conservan() -> None:
    """Camino D3 en True dos veces (dos claves nuevas): no se mezclan."""
    resultado = _merge_courses(
        [_curso("CS101", "Prog I", "100"), _curso("MA101", "Cálculo", "200")]
    )
    assert len(resultado) == 2
    assert {c.codigo for c in resultado} == {"CS101", "MA101"}


# ---------------------------------------------------------------------------
# D3 (False) + D5 (True) — mismo código repetido: se juntan sus secciones.
# ---------------------------------------------------------------------------


def test_curso_repetido_junta_secciones() -> None:
    """Camino D3 False (clave ya vista) + D5 True (secciones nuevas)."""
    resultado = _merge_courses([_curso("CS101", "Prog I", "100"), _curso("CS101", "Prog I", "200")])
    assert len(resultado) == 1
    assert _secciones(resultado[0]) == ["100", "200"]


# ---------------------------------------------------------------------------
# D5 (False) — sección duplicada dentro del merge: no se agrega de nuevo.
# ---------------------------------------------------------------------------


def test_seccion_duplicada_no_se_repite() -> None:
    """Camino D5 en False: la sección "100" ya está vista → se ignora."""
    resultado = _merge_courses(
        [_curso("CS101", "Prog I", "100"), _curso("CS101", "Prog I", "100", "200")]
    )
    assert len(resultado) == 1
    assert _secciones(resultado[0]) == ["100", "200"]


# ---------------------------------------------------------------------------
# D2 — código vacío: la clave cae al nombre (`codigo or nombre`).
# ---------------------------------------------------------------------------


def test_codigo_vacio_usa_el_nombre_como_clave() -> None:
    """Camino D2 (`or`): dos cursos sin código pero mismo nombre → se mergean."""
    resultado = _merge_courses([_curso("", "Química", "300"), _curso("", "Química", "400")])
    assert len(resultado) == 1
    assert _secciones(resultado[0]) == ["300", "400"]


def test_clave_es_insensible_a_mayusculas() -> None:
    """La clave se normaliza a mayúsculas: "cs101" y "CS101" son el mismo curso."""
    resultado = _merge_courses([_curso("cs101", "Prog I", "100"), _curso("CS101", "Prog I", "200")])
    assert len(resultado) == 1
    assert _secciones(resultado[0]) == ["100", "200"]
