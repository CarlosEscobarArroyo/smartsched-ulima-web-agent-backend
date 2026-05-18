from fastapi import APIRouter, File, HTTPException, UploadFile

from app.integrations.bucket.bucket import upload_file

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/")
async def subir_archivo(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo no tiene nombre.")

    data = await file.read()
    try:
        gcs_path = upload_file(file.filename, data, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {exc}") from exc

    return {"status": "success", "path": gcs_path}
