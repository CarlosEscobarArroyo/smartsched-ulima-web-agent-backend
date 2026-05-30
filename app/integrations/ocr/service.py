"""Orquestación del OCR (US-01/US-02): imágenes → Gemini multimodal → `{cursos}`.

Solo imágenes, procesamiento inline (sin GCS) — ver decisión 2026-05-29 en CLAUDE.md.

Las imágenes se pasan DIRECTO a Gemini (multimodal): no se aplanan con Cloud Vision,
porque eso destruía la estructura de la tabla y el modelo asignaba mal los horarios.
`app/integrations/ocr/client.py` (Cloud Vision) queda como pieza huérfana del flujo.
"""

import logging

from app.integrations.ocr.schemas import OCRCurso, OCRExtractionResponse
from app.integrations.ocr.structurer import (
    CourseStructurer,
    ImageInput,
    get_course_structurer,
)

logger = logging.getLogger(__name__)


class UnreadableImageError(Exception):
    """No se pudieron extraer cursos de las imágenes (ilegibles o error del modelo)."""


def _merge_courses(cursos: list[OCRCurso]) -> list[OCRCurso]:
    """Agrupa cursos repetidos en uno solo, juntando sus secciones.

    El modelo a veces emite un curso por cada sección (en cursos con muchas secciones)
    en lugar de agrupar; aquí lo corregimos de forma determinista. La clave es el código
    (o el nombre si el código viene vacío); dentro de un curso, las secciones se
    deduplican por su número conservando el orden de aparición.
    """
    merged: dict[str, OCRCurso] = {}
    for curso in cursos:
        key = (curso.codigo or curso.nombre).strip().upper()
        existing = merged.get(key)
        if existing is None:
            merged[key] = curso
            continue
        vistas = {sec.seccion for sec in existing.secciones}
        for sec in curso.secciones:
            if sec.seccion not in vistas:
                existing.secciones.append(sec)
                vistas.add(sec.seccion)
    return list(merged.values())


class OCRService:
    def __init__(self, structurer: CourseStructurer) -> None:
        self._structurer = structurer

    def extract(self, images: list[ImageInput]) -> OCRExtractionResponse:
        """Estructura las imágenes (bytes, mime) a `{cursos}` con Gemini multimodal.

        Lanza `UnreadableImageError` si no hay imágenes o el modelo falla.
        """
        if not images:
            raise UnreadableImageError("No se recibieron imágenes.")

        try:
            data = self._structurer.structure(images)
        except Exception as exc:
            logger.exception("El estructurador multimodal falló al procesar las imágenes")
            raise UnreadableImageError(str(exc)) from exc

        parsed = OCRExtractionResponse.model_validate(data)
        return OCRExtractionResponse(cursos=_merge_courses(parsed.cursos))


def get_ocr_service() -> OCRService:
    return OCRService(structurer=get_course_structurer())
