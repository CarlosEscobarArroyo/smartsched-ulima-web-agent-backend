"""Normaliza la URL de base de datos para asyncpg (SSL en hosts remotos como Neon)."""

import ssl
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parámetros estilo libpq que asyncpg NO acepta en el query string. Neon/Cloud SQL
# los incluyen en su connection string (p. ej. "?sslmode=require&channel_binding=require"),
# así que se eliminan antes de construir el engine.
_LIBPQ_ONLY = {"sslmode", "channel_binding", "options"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def build_engine_url(raw_url: str) -> tuple[str, dict[str, Any]]:
    """Devuelve (url_limpia, connect_args) lista para `create_async_engine`.

    - Quita los params estilo libpq que asyncpg rechaza.
    - Para hosts remotos (Neon, etc.) exige TLS con verificación de certificado.
      Para localhost no usa SSL (el Postgres de Docker no lo tiene).
    """
    parts = urlsplit(raw_url)
    # Neon/Postgres entregan la URL como "postgresql://" (o "postgres://"); el
    # engine async necesita el driver asyncpg. Se normaliza el esquema para que
    # se pueda pegar la cadena tal cual desde Neon.
    scheme = parts.scheme
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+asyncpg"
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in _LIBPQ_ONLY]
    clean_url = urlunsplit(parts._replace(scheme=scheme, query=urlencode(kept)))

    connect_args: dict[str, Any] = {}
    if (parts.hostname or "") not in _LOCAL_HOSTS:
        connect_args["ssl"] = ssl.create_default_context()
    return clean_url, connect_args
