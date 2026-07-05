# SmartSched ULIMA — Backend (FastAPI)

Backend de SmartSched ULIMA: orquesta el agente IA (`ulima-agent` con Vertex AI ADK), genera combinaciones de horarios sin choques, procesa imágenes con OCR multimodal (Gemini) y expone el panel de administración.

El **frontend** (Next.js) vive en el repo hermano `../smartsched-ulima-web-frontend`.

---

## Stack

- **FastAPI** + **Pydantic v2**
- **SQLAlchemy 2.x async** + **asyncpg**
- **Alembic** (migraciones)
- **Neon** (PostgreSQL 17 serverless — producción y desarrollo)
- **uv** (gestor de dependencias y entorno virtual)
- **Google Gemini** (OCR multimodal) + **Vertex AI ADK** (agente IA)
- **SMTP de Gmail** (envío de emails — reset de contraseña, vía `smtplib`)
- **pytest** + **httpx** + **SQLite in-memory** (tests, sin tocar Neon)

---

## Estructura

Organización **por dominios**: cada feature de negocio vive en `app/domains/<x>/` como carpeta autocontenida. Los clientes hacia sistemas externos son adapters en `app/integrations/`.

```
app/
├── main.py
├── core/
│   ├── config.py          ← settings desde .env (pydantic-settings)
│   └── security.py        ← bcrypt + JWT (python-jose)
├── api/v1/
│   └── router.py          ← agrega todos los routers bajo /api/v1
├── domains/
│   ├── auth/              ← login, JWT, bloqueo, reset de contraseña
│   │   ├── router.py      ← POST /auth/login, GET /auth/me, POST /auth/forgot-password, POST /auth/reset-password
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── models.py      ← ORM PasswordResetToken
│   │   └── deps.py        ← get_current_user, require_role
│   ├── users/             ← ORM User + repositorio
│   │   ├── models.py
│   │   └── repository.py
│   ├── schedules/         ← generación + horarios guardados
│   │   ├── router.py      ← POST /schedules/generate, CRUD /schedules/saved
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── saved_service.py
│   │   └── models.py      ← ORM SavedSchedule
│   ├── admin/             ← panel de administración (US-29/30/31/32)
│   │   ├── router.py      ← CRUD /admin/users, /admin/professors, /admin/courses
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   └── models.py      ← ORM Professor, Course
│   └── chat/              ← proxy al agente IA (in-memory por ahora)
│       ├── router.py      ← POST /chat, CRUD /chat/conversations
│       ├── schemas.py
│       ├── service.py
│       └── store.py
├── integrations/
│   ├── ocr/               ← Gemini multimodal (process-image)
│   ├── generator/         ← backtracking sin choques
│   ├── agent/             ← cliente ulima-agent (ADK in-process)
│   ├── email/             ← SMTP de Gmail (reset de contraseña)
│   │   └── client.py      ← send_reset_email; fallback a log si SMTP sin configurar
│   └── bucket/            ← GCS (huérfano, sin uso en el flujo actual)
├── db/
│   ├── base.py
│   ├── session.py         ← engine async + get_db
│   ├── url.py             ← normaliza la URL de Neon para asyncpg
│   └── migrations/        ← Alembic
│       └── versions/
│           ├── 0001_create_users_table.py
│           ├── 0002_create_saved_schedules.py
│           ├── 0003_create_professors_table.py
│           ├── 0004_create_courses_table.py
│           ├── 0005_add_professor_id_to_courses.py
│           ├── 0006_native_uuid_and_role_enum.py
│           ├── 0007_add_updated_at.py
│           ├── 0008_add_updated_at_defaults.py
│           └── 0009_create_password_reset_tokens.py
└── health/
    └── router.py
tests/
ulima-agent/               ← subproyecto del agente ADK
scripts/                   ← seed_users.py, smoke tests OCR
```

---

## Inicio rápido

```bash
# 1. Entrar a la carpeta del backend
cd smartsched-ulima-web-agent-backend

# 2. Copiar variables de entorno y configurar DATABASE_URL y JWT_SECRET_KEY
cp .env.example .env

# 3. Instalar dependencias (requiere uv)
uv sync

# 4. Aplicar migraciones a la base de datos
uv run alembic upgrade head

# 5. (Opcional) Crear usuarios de prueba
uv run python scripts/seed_users.py

# 6. Levantar el servidor de desarrollo
uv run uvicorn app.main:app --reload
```

API disponible en `http://localhost:8000` — docs interactivas en `http://localhost:8000/docs`.

> Si no tienes `uv`: `pip install uv` o ver https://docs.astral.sh/uv/getting-started/installation/

---

## Setup

### 1. Variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con la connection string de Neon y el JWT secret:

```env
DATABASE_URL=postgresql://usuario:password@host.neon.tech/dbname?sslmode=require
JWT_SECRET_KEY=tu-secreto-aqui

# Opcional — reset de contraseña vía SMTP de Gmail.
# SMTP_PASSWORD es una CONTRASEÑA DE APLICACIÓN (https://myaccount.google.com/apppasswords, requiere 2FA).
SMTP_USER=tucuenta@gmail.com
SMTP_PASSWORD=xxxxxxxxxxxxxxxx
SMTP_FROM_NAME=SmartSched ULIMA
FRONTEND_URL=http://localhost:3000
```

> Usar la string **directa** de Neon (no la `-pooler`). `app/db/url.py` normaliza el esquema y los parámetros SSL automáticamente.
> Sin `SMTP_USER`/`SMTP_PASSWORD`, el backend corre en modo dev: el enlace de reset se imprime en el log del servidor en vez de enviarse por email.

### 2. Dependencias

```bash
uv sync
```

### 3. Migraciones

```bash
uv run alembic upgrade head
```

Aplica las 9 migraciones y crea las tablas `users`, `saved_schedules`, `professors`, `courses` y `password_reset_tokens` en Neon.

### 4. Seed de usuarios (opcional)

```bash
uv run python scripts/seed_users.py
```

Crea `alumno@ulima.edu.pe / Alumno123` (student) y `admin@ulima.edu.pe / Admin1234` (admin).

### 5. Dev server

```bash
uv run uvicorn app.main:app --reload
```

Docs interactivas: http://localhost:8000/docs

---

## Migraciones

```bash
# generar nueva migración a partir de cambios en modelos
uv run alembic revision --autogenerate -m "descripcion"

# aplicar
uv run alembic upgrade head

# revertir una
uv run alembic downgrade -1
```

Al agregar un nuevo modelo ORM, registrarlo en `app/db/migrations/env.py` **y** en `tests/conftest.py`.

---

## Tests

```bash
uv run pytest                              # 78 tests (SQLite in-memory, sin tocar Neon)
uv run pytest tests/test_admin.py          # un archivo
uv run pytest --cov=app --cov-report=term  # cobertura
uv run ruff check .                        # lint
uv run mypy app/                           # type check
```

Los tests usan SQLite en memoria via `conftest.py` (StaticPool + override de `get_db`) — no requieren conexión a Neon.

---

## Endpoints activos

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/api/v1/health` | — | liveness check |
| POST | `/api/v1/auth/login` | — | login → JWT (bloqueo 3 intentos / 15 min) |
| GET | `/api/v1/auth/me` | Bearer | usuario autenticado |
| POST | `/api/v1/auth/forgot-password` | — | solicita reset (siempre 200; email con enlace si existe) |
| POST | `/api/v1/auth/reset-password` | — | cambia contraseña con token (400 si inválido/expirado/usado) |
| POST | `/api/v1/ocr/process-image` | — | imágenes → Gemini multimodal → `{cursos}` |
| POST | `/api/v1/schedules/generate` | — | genera combinaciones sin choques |
| POST | `/api/v1/schedules/saved` | Bearer | guarda horario (tope 10) |
| GET | `/api/v1/schedules/saved` | Bearer | lista horarios guardados |
| GET | `/api/v1/schedules/saved/{id}` | Bearer | detalle con schedule_data |
| DELETE | `/api/v1/schedules/saved/{id}` | Bearer | elimina horario |
| POST | `/api/v1/chat` | — | envía mensaje al agente IA |
| GET/POST | `/api/v1/chat/conversations` | — | lista / crea conversación |
| GET/DELETE | `/api/v1/chat/conversations/{id}` | — | detalle / elimina conversación |
| GET | `/api/v1/admin/stats` | Bearer admin | estadísticas del panel |
| GET/POST | `/api/v1/admin/users` | Bearer admin | lista / crea usuarios |
| PUT/DELETE | `/api/v1/admin/users/{id}` | Bearer admin | actualiza / elimina usuario |
| GET/POST | `/api/v1/admin/professors` | Bearer admin | lista / crea profesores |
| PUT/DELETE | `/api/v1/admin/professors/{id}` | Bearer admin | actualiza / elimina profesor |
| GET/POST | `/api/v1/admin/courses` | Bearer admin | lista / crea cursos |
| PUT/DELETE | `/api/v1/admin/courses/{id}` | Bearer admin | actualiza / elimina curso |

---

## Base de datos (Neon)

**Proveedor:** [Neon](https://neon.tech) — PostgreSQL 17 serverless, región `us-east-1`.
La BD está **fuera de GCP** (excepción aceptada para el free tier). Código 100% Postgres puro → solo cambia `DATABASE_URL` si se migra a otro proveedor.

**Tablas actuales:**

| Tabla | Descripción |
|---|---|
| `users` | Autenticación (rol student/admin, bloqueo por intentos, UUID nativo) |
| `saved_schedules` | Horarios guardados por usuario (FK CASCADE, max 10, schedule_data JSONB) |
| `professors` | Catálogo de docentes (panel admin) |
| `courses` | Catálogo de cursos (FK profesor nullable, prereqs JSONB) |
| `password_reset_tokens` | Tokens de reset (un uso, expiran 60 min, previos se eliminan al re-solicitar) |

---

## GCP

Todo el compute y los servicios de IA operan en el proyecto **`ulima-agent`** (ID real; el nombre display es `smartsched-ulima`):

```bash
gcloud config set project ulima-agent
```

Servicios usados: Vertex AI (agente ADK), Gemini API (OCR), Cloud Run (deploy), Artifact Registry.
