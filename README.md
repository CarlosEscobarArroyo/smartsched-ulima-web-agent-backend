# Smartsched Ulima — Backend (FastAPI)

Backend que orquesta el agente RAG (`ulima-agent` en Vertex AI) y persiste estado en
Postgres / Cloud SQL para la web de Smartsched.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2.x async + asyncpg
- Alembic (migraciones)
- Postgres (local: docker-compose, prod: Cloud SQL en GCP)
- uv (gestor de dependencias)

## Estructura

Organización **por dominios**: cada feature de negocio vive en `app/domains/<x>/`
como carpeta autocontenida (router, schemas, service, models, repository). Los
clientes hacia sistemas externos (Vertex AI, etc.) son adapters y van en
`app/integrations/`. Lo transversal (config, DB, health) vive aparte.

```
app/
├── main.py                          # crea la FastAPI app
├── core/
│   └── config.py                    # settings desde env
├── api/v1/
│   └── router.py                    # agrega los routers de cada dominio
├── domains/                         # ← lógica de negocio
│   └── chat/
│       ├── router.py                # endpoints HTTP
│       ├── schemas.py               # pydantic (request/response)
│       └── service.py               # lógica de negocio
├── integrations/                    # ← adapters a sistemas externos
│   └── agent/
│       └── ulima_agent.py           # cliente hacia Vertex AI / ulima-agent
├── health/                          # liveness/readiness
│   └── router.py
└── db/
    ├── base.py                      # Base SQLAlchemy
    ├── session.py                   # engine + sesión async
    └── migrations/                  # Alembic
tests/
```

> **Nota:** cuando aparezca el primer recurso persistido (ej. `users`, `schedules`)
> se crea `app/domains/<x>/` con: `router.py`, `schemas.py`, `service.py`,
> `models.py`, `repository.py`. Registrá los `models` en `app/db/migrations/env.py`
> para que Alembic los detecte en autogenerate, y agregá el router en
> `app/api/v1/router.py`.

## Setup local

1. **Variables de entorno**

   ```bash
   cp .env.example .env
   ```

2. **Postgres local**

   ```bash
   docker compose up -d
   ```

3. **Dependencias (uv)**

   ```bash
   uv sync
   ```

4. **Migraciones**

   ```bash
   uv run alembic upgrade head
   ```

5. **Correr la app**

   ```bash
   uv run uvicorn app.main:app --reload
   ```

   Docs interactivas: http://localhost:8000/docs

## Migraciones

```bash
# generar nueva migración a partir de cambios en modelos
uv run alembic revision --autogenerate -m "add users table"

# aplicar
uv run alembic upgrade head

# revertir una
uv run alembic downgrade -1
```

## Tests

```bash
uv run pytest
```

## Cloud SQL (producción en GCP)

El código no cambia entre local y prod — solo cambia `DATABASE_URL`:

- **Desde tu Mac → Cloud SQL:** usar
  [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy)
  (abre un túnel local en `127.0.0.1:5432`).
- **Desde Cloud Run → Cloud SQL:** conector nativo vía Unix socket
  (`/cloudsql/PROJECT:REGION:INSTANCE`). Ver `.env.example`.
- **Secrets** (`DATABASE_URL`, claves del agente, etc.) se almacenan en
  **Secret Manager** y se inyectan como env vars al deploy.
- **Migraciones en deploy:** correr `alembic upgrade head` como paso de Cloud Build /
  GitHub Actions antes de promover la nueva revisión de Cloud Run.
