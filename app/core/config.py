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
    gcp_bucket_name: str = "bucket-quickstart_ulima-smartcsched"
    ulima_agent_endpoint: str | None = None

    google_application_credentials: str | None = Field(
        default=None,
        description=(
            "Ruta al JSON del service account para Cloud Vision. Si es None se usan "
            "Application Default Credentials (gcloud auth application-default login en local)."
        ),
    )

    # Autenticación (US-24)
    # ⚠️ En producción inyectar JWT_SECRET_KEY por entorno/Secret Manager.
    jwt_secret_key: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 h (igual al TTL de sesión del FE)
    max_login_attempts: int = 3  # bloqueo tras 3 intentos fallidos
    lockout_minutes: int = 15  # duración del bloqueo

    # Restablecimiento de contraseña (US-25) — email vía SMTP de Gmail.
    # Si smtp_user/smtp_password están vacíos, el backend corre en modo dev:
    # imprime el enlace de reset en el log en vez de enviar el correo.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587  # TLS (STARTTLS); 465 sería SSL directo
    smtp_user: str | None = None  # correo de envío (cuenta Gmail)
    smtp_password: str | None = None  # contraseña de aplicación de Gmail (no la normal)
    smtp_from_name: str = "SmartSched ULIMA"
    frontend_url: str = "http://localhost:3000"
    reset_token_expire_minutes: int = 60


# Singleton (creacional) vía @lru_cache: una única instancia de Settings por
# proceso (se lee el entorno/.env una sola vez y se reutiliza en cada llamada).
@lru_cache
def get_settings() -> Settings:
    return Settings()
