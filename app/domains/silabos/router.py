"""Descarga pública del sílabo de un curso, para compartirlo por el chat del agente.

El agente (tool `descargar_silabo`) devuelve una URL a esta ruta. Es **pública por
id opaco** (el uuid del curso), igual que `fichas/`: el sílabo es material del curso
y así un enlace abierto desde el chat (pestaña nueva, sin `Authorization`) puede
descargarlo. El archivo vive en GCS; aquí se reutiliza la lógica del panel admin
(`admin.service.get_course_syllabus`) que lo baja de GCS y lo entrega.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.admin import service as admin_service

router = APIRouter(prefix="/silabos", tags=["silabos"])


@router.get("/{course_id}")
async def download_silabo(
    course_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    data, content_type, file_name = await admin_service.get_course_syllabus(db, course_id)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )
