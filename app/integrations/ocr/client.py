"""Cliente para Google Cloud Vision API.

Expone una función mínima que recibe los bytes de una imagen y devuelve la
respuesta cruda de `documentTextDetection` como dict (mismo shape que
`ocr_output_example.json`).
"""

from functools import lru_cache

from google.cloud import vision
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict

from app.core.config import get_settings


# Singleton (creacional) vía @lru_cache: un único ImageAnnotatorClient de Cloud
# Vision por proceso. En tests: `_get_client.cache_clear()` antes de patchear.
@lru_cache
def _get_client() -> vision.ImageAnnotatorClient:
    settings = get_settings()
    if settings.google_application_credentials:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_application_credentials
        )
        return vision.ImageAnnotatorClient(credentials=credentials)
    return vision.ImageAnnotatorClient()


# Adapter (estructural): adapta el SDK de Cloud Vision a una función simple del
# dominio (`detect_document_text`), traduciendo bytes → `vision.Image` → dict.
def detect_document_text(image_bytes: bytes) -> dict:
    client = _get_client()
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(f"Cloud Vision error: {response.error.message}")
    return MessageToDict(response._pb, preserving_proto_field_name=False)


def extract_full_text(raw_ocr: dict) -> str:
    """Extrae el texto plano de la respuesta cruda de Cloud Vision.

    El texto extraído debe pasarse al agente LLM, que lo estructura en el
    formato ``{"cursos": [...]}`` esperado por ``parse_ocr_to_sections``.
    """
    return raw_ocr.get("fullTextAnnotation", {}).get("text", "")
