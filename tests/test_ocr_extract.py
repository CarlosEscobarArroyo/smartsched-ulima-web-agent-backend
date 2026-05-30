"""Tests de US-01/US-02: POST /api/v1/ocr/process-image.

Prueban el cableado HTTP, la validación de tipo/tamaño y el manejo de imagen ilegible.
El estructurador multimodal (Gemini) se reemplaza por dobles para no consumir cuota ni
requerir credenciales GCP; la calidad de la extracción no se prueba aquí.
"""

from fastapi.testclient import TestClient

from app.integrations.ocr.schemas import OCRExtractionResponse
from app.integrations.ocr.service import OCRService, UnreadableImageError, get_ocr_service
from app.integrations.ocr.structurer import ImageInput
from app.main import app

URL = "/api/v1/ocr/process-image"

SAMPLE = {
    "cursos": [
        {
            "codigo": "1419",
            "nombre": "COMUNICACION DE DATOS",
            "creditos": 3.0,
            "nivel": 5,
            "secciones": [
                {
                    "seccion": "523",
                    "profesor": "TORRES PAREDES CARLOS MARTIN",
                    "vacantes": 0,
                    "horario": [
                        {"dia": "MIE", "inicio": "11:00", "fin": "13:00", "aula": "850014"}
                    ],
                }
            ],
        }
    ]
}


class FakeStructurer:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def structure(self, images: list[ImageInput]) -> dict:
        return self._payload


def _fake_service(payload: dict = SAMPLE) -> OCRService:
    return OCRService(structurer=FakeStructurer(payload))


def _png(name: str = "horario.png") -> tuple[str, bytes, str]:
    return (name, b"\x89PNG\r\n\x1a\n fake", "image/png")


def test_extrae_cursos_de_imagen_valida() -> None:
    app.dependency_overrides[get_ocr_service] = _fake_service
    client = TestClient(app)
    try:
        res = client.post(URL, files={"files": _png()})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    body = res.json()
    assert body["cursos"][0]["nombre"] == "COMUNICACION DE DATOS"
    assert body["cursos"][0]["secciones"][0]["horario"][0]["dia"] == "MIE"


def test_rechaza_pdf_con_422() -> None:
    app.dependency_overrides[get_ocr_service] = _fake_service
    client = TestClient(app)
    try:
        res = client.post(URL, files={"files": ("malla.pdf", b"%PDF-1.7", "application/pdf")})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422
    assert "no permitido" in res.json()["detail"].lower()


def test_rechaza_imagen_muy_grande_con_422() -> None:
    from app.integrations.ocr import router as ocr_router

    app.dependency_overrides[get_ocr_service] = _fake_service
    big = (b"x" * (ocr_router.MAX_IMAGE_BYTES + 1))
    client = TestClient(app)
    try:
        res = client.post(URL, files={"files": ("grande.png", big, "image/png")})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422
    assert "10 mb" in res.json()["detail"].lower()


def test_imagen_ilegible_devuelve_422() -> None:
    class BoomStructurer:
        def structure(self, images: list[ImageInput]) -> dict:
            raise RuntimeError("modelo no pudo leer la imagen")

    def failing_service() -> OCRService:
        return OCRService(structurer=BoomStructurer())

    app.dependency_overrides[get_ocr_service] = failing_service
    client = TestClient(app)
    try:
        res = client.post(URL, files={"files": _png()})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422
    assert res.json()["detail"] == "Error al procesar. Intente nuevamente."


def test_varias_imagenes_se_pasan_al_estructurador() -> None:
    captured: dict[str, list[ImageInput]] = {}

    class CapturingStructurer:
        def structure(self, images: list[ImageInput]) -> dict:
            captured["images"] = images
            return SAMPLE

    def multi_service() -> OCRService:
        return OCRService(structurer=CapturingStructurer())

    app.dependency_overrides[get_ocr_service] = multi_service
    client = TestClient(app)
    try:
        res = client.post(
            URL,
            files=[
                ("files", ("a.png", b"bytes-A", "image/png")),
                ("files", ("b.png", b"bytes-B", "image/png")),
            ],
        )
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    # Ambas imágenes (bytes + mime) llegan al estructurador multimodal.
    assert [data for data, _ in captured["images"]] == [b"bytes-A", b"bytes-B"]
    assert all(mime == "image/png" for _, mime in captured["images"])


def test_unreadable_image_error_existe() -> None:
    # Sanity: el tipo de error usado por el servicio existe y es una excepción.
    assert issubclass(UnreadableImageError, Exception)
    _ = OCRExtractionResponse  # schema importable
