from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Smartsched Ulima Backend"
    environment: str = Field(default="local", description="local | staging | production")
    debug: bool = False

    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str = Field(
        default="postgresql+asyncpg://smartsched:smartsched@localhost:5432/smartsched",
        description="Async SQLAlchemy URL. En GCP apunta a Cloud SQL vía Auth Proxy o conector.",
    )

    gcp_project_id: str | None = None
    gcp_location: str = "us-central1"
    ulima_agent_endpoint: str | None = None

    google_application_credentials: str | None = Field(
        default=None,
        description=(
            "Ruta al JSON del service account para Cloud Vision. Si es None se usan "
            "Application Default Credentials (gcloud auth application-default login en local)."
        ),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
