from functools import lru_cache

from google.cloud import storage

from app.core.config import get_settings


# Singleton (creacional) vía @lru_cache: un único storage.Client de GCS por
# proceso (evita recrear la conexión/credenciales en cada subida).
# En tests: `_get_client.cache_clear()` antes de patchear.
@lru_cache
def _get_client() -> storage.Client:
    settings = get_settings()
    return storage.Client(project=settings.gcp_project_id)


# Adapter (estructural): adapta el SDK de Google Cloud Storage a una función simple
# del dominio (`upload_file`), escondiendo `storage.Client`/`bucket`/`blob`.
def upload_file(filename: str, data: bytes, content_type: str) -> str:
    """Sube *data* al bucket configurado y devuelve la ruta gs:// del objeto."""
    settings = get_settings()
    client = _get_client()
    bucket = client.bucket(settings.gcp_bucket_name)
    blob = bucket.blob(f"uploads/{filename}")
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{settings.gcp_bucket_name}/uploads/{filename}"


def upload_syllabus(course_id: str, extension: str, data: bytes, content_type: str) -> str:
    """Sube el sílabo de un curso a `syllabi/{course_id}{extension}` y devuelve su gs://.

    Usa una ruta fija por curso (solo varía la extensión), así una re-subida
    **sobrescribe** el sílabo anterior en vez de dejar objetos huérfanos.
    """
    settings = get_settings()
    client = _get_client()
    bucket = client.bucket(settings.gcp_bucket_name)
    blob_name = f"syllabi/{course_id}{extension}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{settings.gcp_bucket_name}/{blob_name}"


def upload_professor_photo(
    professor_id: str, extension: str, data: bytes, content_type: str
) -> str:
    """Sube la foto de un profesor a `professors/{professor_id}{extension}` → gs://.

    Usa una ruta fija por profesor (solo varía la extensión), así una re-subida
    **sobrescribe** la foto anterior en vez de dejar objetos huérfanos.
    """
    settings = get_settings()
    client = _get_client()
    bucket = client.bucket(settings.gcp_bucket_name)
    blob_name = f"professors/{professor_id}{extension}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{settings.gcp_bucket_name}/{blob_name}"


def download_from_gcs(gcs_path: str) -> tuple[bytes, str]:
    """Descarga el objeto en *gcs_path* (`gs://bucket/blob`) → (bytes, content_type).

    Lanza `ValueError` si la ruta no tiene forma `gs://bucket/blob`.
    """
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Ruta GCS inválida: {gcs_path!r}")
    bucket_name, _, blob_name = gcs_path[len("gs://") :].partition("/")
    if not bucket_name or not blob_name:
        raise ValueError(f"Ruta GCS inválida: {gcs_path!r}")
    client = _get_client()
    blob = client.bucket(bucket_name).blob(blob_name)
    data = blob.download_as_bytes()
    return data, blob.content_type or "application/octet-stream"
