"""Conexión de solo lectura a la BD (Neon/Postgres) para las tools del agente.

El agente corre in-process dentro del backend, pero este paquete NO importa `app`
(la dependencia es backend -> ulima-agent; importar `app` la invertiría). Por eso
arma su propio engine async leyendo `DATABASE_URL` del entorno, replicando la
normalización de URL del backend (`app/db/url.py`): quita los parámetros estilo
libpq que asyncpg rechaza y activa TLS con verificación en hosts remotos (Neon).

El engine es perezoso (se crea al primer uso) y único por proceso, para no exigir
`DATABASE_URL` al solo importar el módulo (p. ej. en pruebas que no tocan la BD).
"""

import datetime
import decimal
import os
import ssl
import uuid
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Parámetros estilo libpq que asyncpg NO acepta en el query string (Neon los pone).
_LIBPQ_ONLY = {"sslmode", "channel_binding", "options"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}

_engine: AsyncEngine | None = None


def _build_engine_url(raw_url: str) -> tuple[str, dict[str, Any]]:
    """(url_limpia, connect_args) lista para create_async_engine. Ver app/db/url.py."""
    parts = urlsplit(raw_url)
    scheme = parts.scheme
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+asyncpg"
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in _LIBPQ_ONLY]
    clean_url = urlunsplit(parts._replace(scheme=scheme, query=urlencode(kept)))

    connect_args: dict[str, Any] = {}
    if (parts.hostname or "") not in _LOCAL_HOSTS:
        connect_args["ssl"] = ssl.create_default_context()
    return clean_url, connect_args


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        raw = os.getenv("DATABASE_URL")
        if not raw:
            raise RuntimeError(
                "DATABASE_URL no está definido; el agente no puede consultar la base de datos."
            )
        url, connect_args = _build_engine_url(raw)
        _engine = create_async_engine(
            url, echo=False, pool_pre_ping=True, connect_args=connect_args
        )
    return _engine


def _jsonable(value: Any) -> Any:
    """Convierte tipos de la BD a algo serializable a JSON (para devolver al LLM)."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


async def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Ejecuta un SELECT parametrizado y devuelve filas como dicts serializables.

    Usa siempre parámetros con nombre (`:nombre`) — nunca interpoles valores del
    usuario en el SQL. Solo lectura: la conexión no hace commit.
    """
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [_jsonable(dict(zip(cols, row, strict=False))) for row in result.fetchall()]
