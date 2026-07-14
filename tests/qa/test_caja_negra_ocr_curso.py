"""PRUEBA DE CAJA NEGRA — `OCRCurso` (contrato de un curso estructurado por el OCR).

Objeto bajo prueba: ``app/integrations/ocr/schemas.py`` → ``OCRCurso``. Es el schema
Pydantic con el que se valida cada curso que el OCR (Gemini multimodal, US-01/02)
devuelve al frontend, y también el `response_schema` que fuerza la salida del modelo.

------------------------------------------------------------------------------
¿Por qué caja negra?
------------------------------------------------------------------------------
Solo importan ENTRADAS y SALIDAS: dado un diccionario, ¿el curso es válido y con qué
valores queda? No se mira la implementación de Pydantic. Se usan particiones de
equivalencia (tipos válidos vs. inválidos, campo presente vs. ausente) y valores
por defecto de los campos opcionales.

------------------------------------------------------------------------------
Campos de entrada (5 > 4 requeridos por el criterio)
------------------------------------------------------------------------------
    1. codigo      str, opcional (por defecto "")
    2. nombre      str, OBLIGATORIO
    3. creditos    float, opcional (por defecto 0.0)
    4. nivel       int, opcional (por defecto 0)
    5. secciones   list[OCRSeccion], opcional (por defecto [])
"""

import pytest
from pydantic import ValidationError

from app.integrations.ocr.schemas import OCRCurso

# ---------------------------------------------------------------------------
# Partición: entrada completamente válida y valores por defecto.
# ---------------------------------------------------------------------------


def test_curso_valido_completo() -> None:
    curso = OCRCurso.model_validate(
        {
            "codigo": "CS101",
            "nombre": "Programación I",
            "creditos": 4.0,
            "nivel": 1,
            "secciones": [{"seccion": "100", "profesor": "Docente X", "vacantes": 30}],
        }
    )
    assert curso.codigo == "CS101"
    assert curso.creditos == 4.0
    assert len(curso.secciones) == 1


def test_solo_nombre_aplica_valores_por_defecto() -> None:
    """Solo `nombre` es obligatorio; el resto toma su valor por defecto."""
    curso = OCRCurso.model_validate({"nombre": "Química General"})
    assert curso.codigo == ""
    assert curso.creditos == 0.0
    assert curso.nivel == 0
    assert curso.secciones == []


# ---------------------------------------------------------------------------
# Partición inválida: falta el único campo obligatorio.
# ---------------------------------------------------------------------------


def test_falta_nombre_es_invalido() -> None:
    with pytest.raises(ValidationError):
        OCRCurso.model_validate({"codigo": "CS101"})


# ---------------------------------------------------------------------------
# Campo `creditos` (float): partición numérica válida vs. no numérica.
# ---------------------------------------------------------------------------


def test_creditos_numerico_en_texto_se_convierte() -> None:
    """Partición válida: "3.5" (numérico en texto) se coacciona a float."""
    curso = OCRCurso.model_validate({"nombre": "X", "creditos": "3.5"})
    assert curso.creditos == 3.5


def test_creditos_no_numerico_es_invalido() -> None:
    """Partición inválida: texto no numérico → error de validación."""
    with pytest.raises(ValidationError):
        OCRCurso.model_validate({"nombre": "X", "creditos": "cuatro"})


# ---------------------------------------------------------------------------
# Campo `nivel` (int): partición entera válida vs. no entera.
# ---------------------------------------------------------------------------


def test_nivel_entero_en_texto_se_convierte() -> None:
    curso = OCRCurso.model_validate({"nombre": "X", "nivel": "5"})
    assert curso.nivel == 5


def test_nivel_no_entero_es_invalido() -> None:
    with pytest.raises(ValidationError):
        OCRCurso.model_validate({"nombre": "X", "nivel": "quinto"})


# ---------------------------------------------------------------------------
# Campo `secciones` (lista anidada): partición de tipo incorrecto.
# ---------------------------------------------------------------------------


def test_secciones_no_es_lista_es_invalido() -> None:
    """`secciones` debe ser una lista; un string no lo es → error."""
    with pytest.raises(ValidationError):
        OCRCurso.model_validate({"nombre": "X", "secciones": "no-es-lista"})
