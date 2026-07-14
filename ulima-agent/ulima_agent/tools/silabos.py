"""Tool del agente para compartir el SÍLABO (PDF/DOC) de un curso por el chat.

Consulta la BD (Neon) por el curso y, si tiene un sílabo cargado (que un admin
subió a GCS desde el panel de administración), devuelve una URL de descarga servida
por `GET /api/v1/silabos/{course_id}`. El frontend detecta esa URL en la respuesta y
la muestra como una tarjeta de descarga en el chat. La URL es pública por id opaco
(el uuid del curso), igual que las fichas, para que el navegador la abra sin
`Authorization`.
"""

import logging
import os

from ..db import fetch_all

# Mismo emparejamiento de nombres que las tools de texto y las fichas: todas las
# palabras, sin importar orden ni acentos. Antes un `c.name ILIKE '%...%'` fallaba con
# tildes ("investigacion" no casaba con "Investigación") o con el orden de las palabras.
from .academic import _name_where

logger = logging.getLogger(__name__)

_ERROR_MSG = "No se pudo consultar el sílabo en este momento."


def _sql_silabo(where_nombre: str) -> str:
    """SELECT del sílabo: coincide por código exacto O por nombre (todas las palabras,
    sin orden ni acentos; `where_nombre` lo arma `_name_where`)."""
    return f"""
SELECT c.id AS id, c.code AS codigo, c.name AS nombre,
       c.syllabus_file_name AS archivo, c.syllabus_gcs_path AS gcs_path
FROM courses c
WHERE lower(c.code) = lower(:q) OR ({where_nombre})
ORDER BY (lower(c.code) = lower(:q)) DESC, c.name
LIMIT 1
"""


def _build_silabo_url(course_id: str) -> str:
    """URL a la descarga del sílabo. Absoluta si `AGENT_PUBLIC_BASE_URL` está definido."""
    base = (os.getenv("AGENT_PUBLIC_BASE_URL") or "").rstrip("/")
    path = f"/api/v1/silabos/{course_id}"
    return f"{base}{path}" if base else path


async def descargar_silabo(curso: str) -> dict:
    """Comparte el SÍLABO (PDF/DOC) de un curso para descargarlo desde el chat.

    Busca el curso por código o nombre y, si tiene un sílabo cargado, devuelve una
    "url" de descarga. Úsala cuando el estudiante pida el sílabo de un curso
    ("dame el sílabo", "descargar el sílabo", "el syllabus de X", "el sílabo de X").
    Comparte la "url" tal cual en tu respuesta, en texto plano: el chat la muestra
    como un botón de descarga. Si "tiene_silabo" es false, avisa con honestidad que
    ese curso aún no tiene el sílabo cargado.

    Args:
        curso: Código exacto (p. ej. "650059") o nombre/parte del nombre del curso.

    Returns:
        dict con "encontrado" (bool). Si el curso existe, incluye "tiene_silabo" (bool);
        si es true, también "url", "titulo" y "archivo".
    """
    curso = (curso or "").strip()
    if not curso:
        return {"encontrado": False, "mensaje": "Indica el código o nombre del curso."}
    try:
        where_nombre, p_nombre = _name_where("c.name", curso)
        params = {"q": curso, **p_nombre}
        filas = await fetch_all(_sql_silabo(where_nombre), params)
    except Exception:
        logger.exception("descargar_silabo falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    if not filas:
        return {
            "encontrado": False,
            "mensaje": f"No se encontró un curso con código o nombre '{curso}'.",
        }
    datos = filas[0]
    titulo = f"{datos.get('codigo')} — {datos.get('nombre')}"
    if not datos.get("gcs_path"):
        return {
            "encontrado": True,
            "tiene_silabo": False,
            "titulo": titulo,
            "mensaje": f"El curso {titulo} todavía no tiene un sílabo cargado en el sistema.",
        }
    return {
        "encontrado": True,
        "tiene_silabo": True,
        "titulo": titulo,
        "archivo": datos.get("archivo"),
        "url": _build_silabo_url(datos["id"]),
    }
