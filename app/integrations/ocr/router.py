"""Router del OCR (US-01/US-02): `POST /api/v1/ocr/process-image`.

Recibe una o varias imágenes (FormData campo `files`) y se las pasa directo a Gemini
multimodal (inline, sin GCS) para devolver los cursos detectados. Solo imágenes; PDF se rechaza.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.integrations.ocr.schemas import OCRExtractionResponse
from app.integrations.ocr.service import OCRService, UnreadableImageError, get_ocr_service
from app.integrations.ocr.structurer import ImageInput

router = APIRouter(prefix="/ocr", tags=["ocr"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
PROCESSING_ERROR = "Error al procesar. Intente nuevamente."

OCRServiceDep = Annotated[OCRService, Depends(get_ocr_service)]


@router.post("/process-image", response_model=OCRExtractionResponse)
async def process_image(
    service: OCRServiceDep,
    files: Annotated[list[UploadFile], File(...)],
) -> OCRExtractionResponse:
    if not files:
        raise HTTPException(status_code=422, detail="Debe enviar al menos una imagen.")

    images: list[ImageInput] = []
    for file in files:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Tipo de archivo no permitido: {file.content_type or 'desconocido'}. "
                    "Solo se aceptan imágenes PNG, JPEG o WEBP."
                ),
            )
        data = await file.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=422,
                detail=f"'{file.filename}' supera el tamaño máximo de 10 MB.",
            )
        images.append((data, file.content_type))

    try:
        # La llamada al modelo es bloqueante: se corre en threadpool para no bloquear el loop.
        return await run_in_threadpool(service.extract, images)
    except UnreadableImageError:
        raise HTTPException(status_code=422, detail=PROCESSING_ERROR) from None
