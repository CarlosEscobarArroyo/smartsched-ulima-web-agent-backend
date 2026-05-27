from functools import lru_cache

from google.cloud import storage

from app.core.config import get_settings


@lru_cache
def _get_client() -> storage.Client:
    settings = get_settings()
    return storage.Client(project=settings.gcp_project_id)


def upload_file(filename: str, data: bytes, content_type: str) -> str:
    """Sube *data* al bucket configurado y devuelve la ruta gs:// del objeto."""
    settings = get_settings()
    client = _get_client()
    bucket = client.bucket(settings.gcp_bucket_name)
    blob = bucket.blob(f"uploads/{filename}")
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{settings.gcp_bucket_name}/uploads/{filename}"
