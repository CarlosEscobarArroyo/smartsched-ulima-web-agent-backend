# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⚠️ GCP — PROYECTO OBLIGATORIO (NO USAR OTRO)

**Todo este proyecto (frontend, backend y agente ADK) se despliega y opera EXCLUSIVAMENTE en:**

- **Project ID** (lo que usan `gcloud`/deploy): **`ulima-agent`**
- **Project name** (display, NO usar como ID): `smartsched-ulima`
- **Project number:** `563034868757`
- **Cuenta con acceso:** `carlos.escobar.arroyo@gmail.com`

⚠️ Ojo: `smartsched-ulima` es el **nombre**, no el ID. El ID real es **`ulima-agent`**. NUNCA usar otro proyecto GCP (p. ej. `pe-fcor-ec-coea-explore-dev` u otro que aparezca en `gcloud config`). Antes de cualquier `gcloud`/`gsutil`/deploy, fijar el proyecto:

```bash
gcloud config set project ulima-agent
```

Aplica a Cloud Run, Cloud Build, Vertex AI (agente), Cloud Storage (bucket OCR), Cloud Vision, Artifact Registry y todo recurso GCP.

---

## NAVEGACION ENTRE REPOSITORIOS — LEER SIEMPRE

Este CLAUDE.md vive en el **backend**: `smartsched-ulima-web-agent-backend`.
El **frontend** está en un repositorio hermano. Para acceder:

```bash
cd ../smartsched-ulima-web-frontend
```

La mayoría de historias de usuario requieren cambios en ambos repos.
**Al terminar de trabajar en el frontend, SIEMPRE volver al backend:**

```bash
cd ../smartsched-ulima-web-agent-backend
```

---

## Proyecto: SmartSched-Ulima — Release 01

Aplicación web para estudiantes de la Universidad de Lima: generación de horarios académicos sin choques a partir de screenshots, autenticación, edición manual, exportación a PDF, reseñas de profesores, chat con agente IA y panel de administración.

---

## Comandos de desarrollo

### Backend (este repo)

```bash
uv sync                                    # instalar dependencias
uv run uvicorn app.main:app --reload       # dev server (http://localhost:8000/docs)
uv run pytest                              # todos los tests
uv run pytest tests/test_health.py         # un archivo
uv run pytest tests/test_x.py::test_fn     # una función
uv run pytest --cov=app --cov-report=term  # cobertura
uv run ruff check .                        # lint
uv run ruff check --fix .                  # lint + autofix
uv run mypy app/                           # type check
docker compose up -d                       # Postgres local (user/pass/db: smartsched)
uv run alembic upgrade head                # aplicar migraciones
uv run alembic revision --autogenerate -m "descripcion"  # generar migración
uv run alembic downgrade -1                # revertir última migración
uv run python scripts/ocr_smoke.py <img>   # smoke test OCR (consume cuota real)
```

### Frontend (../smartsched-ulima-web-frontend)

```bash
npm install          # instalar dependencias
npm run dev          # dev server Next.js (http://localhost:3000)
npm run build        # build de producción
npm run lint         # ESLint
```

---

## Arquitectura backend

FastAPI + SQLAlchemy async + asyncpg + Alembic + Google Cloud (Vision, Storage, Vertex AI).

### Estructura por dominios

- **`app/domains/<nombre>/`** — lógica de negocio. Cada dominio: `router.py`, `schemas.py`, `service.py`, opcionalmente `models.py` y `repository.py`.
  - `chat/` — proxy al agente IA en Vertex AI.
  - `schedules/` — modelos de dominio (Curso, Seccion, Horario).
  - `users/` — modelos de dominio (Alumno, Profesor).
- **`app/integrations/<nombre>/`** — adapters a sistemas externos:
  - `agent/` — cliente Vertex AI (actualmente stub).
  - `ocr/` — Cloud Vision `documentTextDetection`.
  - `bucket/` — subida a GCS, router montado en `/api/v1/upload`.
  - `generator/` — algoritmo puro de backtracking para combinaciones sin conflicto.
- **`app/core/config.py`** — `Settings` con pydantic-settings, cacheado con `lru_cache`.
- **`app/db/`** — engine async, sesión, migraciones Alembic. Importar nuevos models en `app/db/migrations/env.py`.
- **`app/api/v1/router.py`** — agrega todos los routers bajo `/api/v1`.

### Flujo OCR → generación de horarios

1. Imagen(es) enviada(s) a `/api/v1/ocr/process-image` (inline, sin GCS).
2. **Gemini multimodal** (`ocr/structurer.py`) recibe la imagen DIRECTA y devuelve JSON `{"cursos": [...]}`. Ya **no** se usa Cloud Vision para aplanar a texto (destruía la estructura de la tabla y el modelo asignaba mal los horarios). `ocr/client.py` quedó huérfano.
3. `service._merge_courses()` agrupa de forma determinista los cursos que el modelo a veces emite duplicados (uno por sección).
4. `parse_ocr_to_sections()` → lista de `ClassSection`.
5. `generate_schedules()` → combinaciones sin conflicto via backtracking.

### Arquitectura frontend

Next.js 16 + React 19 + Tailwind 4 + Zod 4 + Lucide icons.

- **`src/app/`** — App Router con route groups: `(public)/` (login) y `(protected)/` (dashboard, generator, ai-agent, professors, profile, settings, admin/*).
- **`src/features/<nombre>/`** — feature modules autocontenidos (components, hooks, api, types, schemas). Features actuales: `auth`, `dashboard`, `schedule-generator`, `ai-agent`, `professors`, `profile`, `settings`, `admin/` (accounts, courses, professors).
- **`src/components/ui/`** — componentes reutilizables (Button, Input, Card, Dialog, Select, etc.).

---

## Estado de integración Frontend ↔ Backend

> **Auditoría: 2026-05-28** (snapshot point-in-time — verificar contra el código antes de citar).
> Esta sección es el punto de partida real para conectar ambos repos. Reemplaza cualquier
> creencia previa de que las historias ya estaban "cerradas": **a hoy NO hay ninguna historia
> conectada de extremo a extremo (FE↔BE).**

> **🟢 Actualización 2026-05-29 — US-12 (Agente IA) conectada FE↔BE (fase in-memory).**
> Es la **primera historia conectada de extremo a extremo**. Resumen de lo construido:
> - **Agente ADK real** en proyecto embebido `ulima-agent/` (paquete `ulima_agent`, scaffold `agents-cli`),
>   corriendo **in-process** en el backend vía `InMemoryRunner.run_async` (NO Agent Engine remoto).
>   Conectado como dependencia editable (`[tool.uv.sources]`). Modelo `gemini-flash-latest`,
>   instrucción en español (asesor académico, 3 temas), solo conocimiento del LLM (sin tools de datos).
> - **GCP:** usa el proyecto **`ulima-agent`** (pineado en `ulima_agent/agent.py` vía `GOOGLE_CLOUD_PROJECT`).
> - **Endpoints chat:** `POST /chat`, `GET/POST/DELETE /chat/conversations`, `GET /chat/conversations/{id}`.
>   Conversaciones **in-memory** (`app/domains/chat/store.py`) — sin DB, sin auth (decisión de fase).
> - **Avatar** del agente servido desde el backend en `/static/chatbot.png` (mount `StaticFiles`).
> - **Frontend** `features/ai-agent`: mocks reemplazados por llamadas reales (`api.ts`), un solo botón
>   "Nueva conversación" (sin los 3 modos), layout full-bleed, eliminar conversaciones, avatar.
> - **Pendiente para cerrar la DoD formal:** CA-2 auth real (US-24), CA-3 (<3s) sin medir, persistencia
>   `Conversation`/`Message` + Alembic, eval del agente, deploy a Cloud Run, code review + merge. Sin commitear aún.

> **🟢 Actualización 2026-06-01 — US-13/US-14 PERSISTENCIA EN BD del chat (backend). Sin commitear.**
> Se eliminó el `app/domains/chat/store.py` in-memory y el dominio `chat/` pasó al patrón estándar (como `auth/`/`admin/`):
> - **ORM** `chat/models.py`: `Conversation` (id, **`user_id` FK→users CASCADE**, title, mode, adk_session_id, created_at, updated_at) + `Message` (id, conversation_id FK CASCADE, role, content, created_at). `Message.created_at` se fija **en Python al insertar** para un orden estable user→assistant (un `server_default now()` daría a ambos el mismo instante de transacción).
> - **`chat/repository.py`** (consultas async que **siempre filtran por `user_id`** → ownership) + **`chat/service.py`** (`ChatService(agent, db)`, métodos async por usuario) + **`chat/router.py` ahora protegido con `get_current_user`**: TODOS los endpoints de chat exigen `Authorization: Bearer`; ver/eliminar/enviar valida dueño → **404 si la conversación no es suya** (no se filtra existencia).
> - **Migración `0010_create_conversations_and_messages`** (down_revision `0009`; UUID nativo, FKs CASCADE, índices en `user_id`/`conversation_id`). Registrada en `migrations/env.py` y `tests/conftest.py`. DDL offline validado para Postgres.
> - **Sesión ADK efímera resuelta:** nuevo `UlimaAgentClient.ensure_session(session_id, user_id)` revalida la sesión in-memory contra el runner y la **recrea si se perdió tras un reinicio** (el historial visible no se pierde: vive en la BD). Crear conversación ya NO crea sesión ADK (perezosa al primer mensaje).
> - **Tests** `tests/test_chat.py` reescritos (fake agent vía override de `get_ulima_agent` + token + SQLite, cubre persistencia, historial multi-petición y aislamiento por usuario): **13 pasan → suite total 90 passed.** ruff/mypy limpios en `chat/` (se resolvió de paso la deuda mypy de `chat/router.py:44`).
> - **✅ FE cableado + migración aplicada (2026-06-01):** `features/ai-agent/api.ts` ya envía `Authorization: Bearer` (`getToken()`); la carga inicial se movió al **cliente** (`AIAgent.tsx` recarga en `useEffect` de montaje, porque el token vive en localStorage y la página es server component). Migración **`0010` aplicada a Neon** (`alembic upgrade head` → 0009→0010 head). **Smoke test EN VIVO contra Neon OK:** 401 sin token; crear/listar/detalle/eliminar con token; 404 tras borrar.

> **🟢 Actualización 2026-06-01 (noche) — Fix MEMORIA del agente: rehidratación de sesión ADK.**
> Las sesiones del `InMemoryRunner` son efímeras: tras un reinicio (`--reload`) o al **reabrir una conversación vieja**, la sesión ADK se perdía y el agente olvidaba el contexto aunque la BD mostrara el historial. **Fix:** `UlimaAgentClient.ensure_session(session_id, user_id, history)` — cuando crea una sesión nueva, la **siembra con el historial persistido** (`_seed_history` → `session_service.append_event` con eventos `role="user"`/`"model"`); si la sesión sigue viva, se reutiliza (no se siembra → no duplica). El `ChatService.send_message` pasa `history=[(m.role,m.content) for m in conversation.messages]`. **VERIFICADO EN VIVO:** msg1 "me llamo Pedro… Cálculo I" → `touch app/main.py` (reload, borra runner) → msg2 → "Recuerdo… Pedro Quispe… Cálculo I". Test `test_rehidrata_sesion_con_historial`; **suite 91 passed**, ruff limpio (mypy: solo deuda preexistente de `agent/` por stubs). ⚠️ Nota: el ejemplo inicial de Carlos ("¿sabes cómo me llamo?") era engañoso — el saludo "Hola Carlos" lo pone el FE (`initialMessages.ts`, estático), no el agente. Al tocar ADK se usó el skill `google-agents-cli-adk-code`.

> **🟢 Actualización 2026-05-31 (tarde) — US-09 Guardar horario CERRADA end-to-end (FE↔BE↔Neon). Sin commitear.**
> El backend de US-09 ya estaba; esta tanda completó el **FE** y agregó el **detalle**:
> - **Nuevo endpoint BE:** `GET /api/v1/schedules/saved/{id}` → `SavedScheduleDetailOut` = `{id, name, savedAt, scheduleData}` (la lista NO expone el blob; el detalle SÍ, para re-renderizar). `saved_service.get_saved_schedule` (404 si no es del usuario). 3 tests nuevos → **suite 43 passed**, ruff/mypy limpios.
> - **FE:** módulo cliente `features/schedule-generator/savedSchedules.ts` (save/list/detail/delete con `Authorization: Bearer` vía `getToken()`; errores tipados `NotAuthenticatedError`/`SaveLimitError`); botón **"Guardar"** del `ScheduleModal` ya **habilitado** (se quitó el "Pronto") → abre `SaveScheduleDialog` (nombrar, validación, 409/sesión); tabla extraída a **`ScheduleGrid`** (reutilizable); **"Mis horarios"** del perfil ahora es real (`SavedSchedulesSection` client: fetch + eliminar con confirmación + "Ver" → `ViewScheduleDialog` re-renderiza el horario guardado). Se quitó el mock `schedules` de `getProfile`.
> - **⚠️ Importante:** el body de guardar usa **`schedule_data` (snake_case)** — `SavedScheduleCreate` NO tiene `populate_by_name`. Las llamadas son **client-side fetch** (no server actions) porque el token vive en localStorage. CORS del backend ya permite `Authorization`.
> - **Verificado en vivo contra Neon:** guardar 201, listar 200 (sin blob), detalle 200 (con `scheduleData`), detalle sin token 401, eliminar 204, listar tras borrar `[]`/200. FE `tsc`+`lint`+`build` limpios. **Falta solo:** prueba manual en navegador (click "Guardar" → modal → perfil).
>
> **🟢 Actualización 2026-05-31 — Neon CONECTADO y login probado EN VIVO. Sin commitear.**
> La BD ya no es teoría: Carlos creó el proyecto en Neon (región `us-east-1`, **Postgres 17.10**) y pegó el `DATABASE_URL` directo (no `-pooler`) + un `JWT_SECRET_KEY` real en `backend/.env` (ignorado por git).
> - **Migraciones aplicadas a Neon:** `uv run alembic upgrade head` corrió **0001 + 0002** → existen las tablas `users`, `saved_schedules` y `alembic_version` (verificado por `information_schema`).
> - **Seed corrido:** `scripts/seed_users.py` (idempotente) → `alumno@ulima.edu.pe/Alumno123` (student) y `admin@ulima.edu.pe/Admin1234` (admin).
> - **Login end-to-end OK (curl contra uvicorn real):** alumno → 200 `role=student` con JWT válido; admin → 200 `role=admin`; `/auth/me` con token → 200; password incorrecto → 401; `/auth/me` sin token → 401.
> - **Fix en `app/db/url.py`:** `build_engine_url` ahora **normaliza el esquema `postgresql://`→`postgresql+asyncpg://`** (además de limpiar `sslmode`/`channel_binding` y agregar SSL), para poder pegar la cadena de Neon tal cual.
>
> **🟢 Actualización 2026-05-30 — US-24 (Auth + DB base) y US-09 backend (Guardar horario). Sin commitear.**
> Primera **persistencia real** del proyecto (antes todo eran dataclasses, 0 migraciones). Construido **solo backend** salvo el cableado FE del login.
>
> **Decisiones de esta sesión:**
> - **Estrategia de token = `Bearer` + localStorage** (resuelve el "PENDIENTE" del 2026-05-28). El FE manda `Authorization: Bearer <jwt>`.
> - **Proveedor de BD = Neon** (Postgres serverless, free tier real, escala a cero) en vez de Cloud SQL (costo; se acabaron créditos GCP). ⚠️ Neon está **fuera de GCP** — excepción aceptada solo para la BD; compute/Vertex/agente/bucket siguen en `ulima-agent`. Código es Postgres puro → **solo cambia `DATABASE_URL`**.
> - **Modelo de datos completo** diseñado en [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md) (diagrama ER Mermaid + 11 tablas). `section_times` normalizada; prereqs M2M auto-ref; JSONB solo para `saved_schedules.schedule_data`; profesor ≠ usuario; rol canónico `student/admin`; ids UUID string.
>
> **US-24 Auth (backend):** `app/core/security.py` (bcrypt directo — se descartó passlib, rompía con bcrypt ≥4.1 — + JWT con python-jose), `app/core/config.py` (`jwt_secret_key`, `access_token_expire_minutes=480`, `max_login_attempts=3`, `lockout_minutes=15`), `app/domains/users/models.py` (ORM `User` + enum `UserRole`; se **conservan** las dataclasses `Usuario/Alumno/Profesor` que usa `schedules/models.py`), `users/repository.py`, dominio `app/domains/auth/` (`schemas`, `service`, `deps`, `router`). Endpoints: `POST /auth/login` (401 inválido; **423 bloqueo tras 3 intentos/15 min**; resetea contador al éxito) y `GET /auth/me`. Dependencies reutilizables **`get_current_user`** y **`require_role(UserRole.ADMIN)`**. Migración **`0001_create_users_table`**. `scripts/seed_users.py` (idempotente: `alumno@ulima.edu.pe/Alumno123` student, `admin@ulima.edu.pe/Admin1234` admin). Deps nuevas: `pydantic[email]`, `bcrypt` (quitado `passlib`), `aiosqlite` (dev).
>
> **US-09 Guardar horario (backend):** ORM `SavedSchedule` (`schedule_data` = `JSON().with_variant(JSONB,"postgresql")` para que los tests SQLite funcionen), migración **`0002_create_saved_schedules`** (FK `user_id` CASCADE + index), `schedules/saved_service.py` (create/list/delete, **tope `MAX_SAVED=10` → 409**, 404 si el horario no es del usuario), endpoints protegidos con `get_current_user`: `POST/GET/DELETE /api/v1/schedules/saved`. `SavedScheduleOut` = `{id, name, savedAt}` (campo `saved_at` con `alias="savedAt"`).
>
> **Infra Neon:** `app/db/url.py` (`build_engine_url`) normaliza la URL (quita `sslmode`/`channel_binding`/`options` que asyncpg rechaza) y activa **SSL con verificación** en hosts remotos; localhost sin SSL. Usado por `session.py` y `migrations/env.py`. `.env.example` documenta el formato Neon (usar string **directo**, NO `-pooler`).
>
> **Tests para BD sin Postgres:** `tests/conftest.py` levanta **SQLite en memoria** (StaticPool) + override de `get_db` + httpx `AsyncClient`. `tests/test_auth.py` (10) y `tests/test_saved_schedules.py` (5). **Suite total: 40 passed.** ruff/mypy limpios en archivos nuevos (la deuda preexistente en `bucket/`, `ocr/client.py`, `agent/`, `chat/router.py:44` sigue ahí, NO es de esta sesión).
>
> **FE del login cableado** (ver CLAUDE.md del frontend): `loginAction` real, `session.ts`, redirección y guardia por rol. `tsc`/`lint`/`build` limpios.
>
> **✅ VERIFICADO EN VIVO (2026-05-31)** contra Neon: `alembic upgrade head` (0001+0002), `seed_users.py` y login real OK (ver bloque verde del 2026-05-31 arriba). Ya NO se usa Docker/Postgres local — la BD es Neon remota.

### Resumen ejecutivo

- **Backend = esqueleto + flujo de horarios.** Routers montados en `app/api/v1/router.py`: health, chat, upload, **schedules (`generate`)** y **ocr (`process-image`)**. Sigue **sin auth, sin persistencia real, sin migraciones**.
- **Frontend = mock salvo 3 features reales.** ~25 *server actions* (`'use server'`) devuelven datos hardcodeados con `setTimeout`; ya van **contra el backend real**: ai-agent (chat), **OCR** y **generación de horarios**. **No existe aún un cliente HTTP compartido genérico** (cada feature resuelve su red).
- **Modelos de dominio son `dataclasses`, no SQLAlchemy** → nada se persiste todavía (incl. el dominio `schedules/`).

### Endpoints backend realmente vivos hoy

> Tabla actualizada al **2026-05-29** (incluye US-01/02 OCR, US-07 generar, US-12 chat).

| Método | Ruta | Real | Notas |
|---|---|---|---|
| GET | `/api/v1/health` | ✅ | status + environment |
| POST | `/api/v1/auth/login` | ✅ | **US-24**: email+password → `{access_token, token_type, user}`. 401 inválido / 423 bloqueo (3 intentos/15 min). DB = Neon. **Probado en vivo (2026-05-31)** + tests SQLite. |
| GET | `/api/v1/auth/me` | ✅ | **US-24**: valida el JWT (`Authorization: Bearer`) y devuelve el usuario. |
| POST | `/api/v1/schedules/saved` | ✅ | **US-09** 🔒: guarda horario del usuario (tope 10 → 409). Body `{name, schedule_data}` → `{id, name, savedAt}`. |
| GET | `/api/v1/schedules/saved` | ✅ | **US-09** 🔒: lista los horarios guardados del usuario (ligero, sin blob). **Conectado al FE** (perfil → Mis horarios). |
| GET | `/api/v1/schedules/saved/{id}` | ✅ | **US-09** 🔒: detalle con `scheduleData` (para re-renderizar). 404 si no es del usuario. **Conectado al FE** (botón "Ver"). |
| DELETE | `/api/v1/schedules/saved/{id}` | ✅ | **US-09** 🔒: elimina (204; 404 si no es del usuario). **Conectado al FE** (eliminar en Mis horarios). |
| POST | `/api/v1/chat` | ✅ | **US-12/13** 🔒: agente ADK in-process + persiste user/assistant. Body `{conversation_id, message}` → `{reply, conversation_id}`. 404 si la conversación no es del usuario. |
| GET | `/api/v1/chat/conversations` | ✅ | **US-13** 🔒: lista conversaciones del usuario (persistidas, ordenadas por `updated_at`) |
| POST | `/api/v1/chat/conversations` | ✅ | **US-13** 🔒: crea conversación ligada al usuario (sesión ADK perezosa) |
| GET | `/api/v1/chat/conversations/{id}` | ✅ | **US-13** 🔒: detalle con mensajes (404 si no es suya) |
| DELETE | `/api/v1/chat/conversations/{id}` | ✅ | **US-14** 🔒: elimina conversación del usuario (204; 404 si no es suya) |
| GET | `/static/chatbot.png` | ✅ | avatar del agente (StaticFiles) |
| POST | `/api/v1/upload/` | ✅ | sube 1 archivo a GCS. **Huérfano**: el FE no lo llama (ver decisión OCR del 2026-05-29). |
| POST | `/api/v1/upload/multiple/` | ✅ | sube varios archivos a GCS. Huérfano (sin uso en el flujo). |
| POST | `/api/v1/schedules/generate` | ✅ | **US-07**: genera combinaciones sin cruces. Reúsa `generator.py`. `MAX_OPTIONS=20`, `truncated`, timeout 2 min. Sin auth. **Conectado al FE** (`generateSchedules.ts` hace fetch; verificado en vivo 2026-05-29). |
| POST | `/api/v1/ocr/process-image` | ✅ | **US-01/02**: imágenes (png/jpeg/webp, ≤10 MB) → **Gemini multimodal** (imagen directa, inline, sin GCS) → `{cursos}`. Tipo inválido/PDF/grande → 422; imagen ilegible → 422 "Error al procesar...". Sin auth. Verificado end-to-end (2026-05-29): 3 cursos/21 secciones correctos. **Conectado al FE** (`extractCoursesFromFile.ts`, sin fallback: muestra el error real). |

> **🟢 Actualización 2026-05-29 — `POST /schedules/generate` implementado (backend).** Dominio `app/domains/schedules/` (`schemas.py`/`service.py`/`router.py`) que adapta el contrato del FE (strings `horarios`/`blockedSlots`) → `TimeBlock`, reúsa `generate_schedules()` y reconstruye el shape `{id, options:[{id, courses:[…selectedSection]}], truncated}`. Restricciones imposibles → 200 con `options:[]`; sin cursos seleccionados → 422. Tests en `tests/test_schedules_generate.py` (8), ruff/mypy OK. **FE conectado** (`generateSchedules.ts` hace fetch; verificado en vivo 2026-05-29: payload del FE → opciones correctas, bloqueos respetados). **Pendiente:** auth para guardar (US-09), click-through del UI corriendo, commit.

> **🔎 2026-05-29 — Caso "solo 1 combinación" reportado por Carlos: el algoritmo es correcto.** Input: 650078 ANALÍTICA (1 sección fija 853: LUN/JUE 18-20) + 650065 CIBERSEGURIDAD (4 secciones; 754 y 755 chocan en JUE 19-22 con la 853). El backend devuelve **2 opciones** (853+751, 853+753) — verificado por curl en vivo, por réplica de la lógica del FE, y blindado con `test_caso_analitica_ciberseguridad_da_dos_opciones`. El "1 opción" que ve Carlos es de **runtime, no de código**: sospechoso nº1 = `localStorage['smartsched.wizard'].blockedSlots` que persiste entre reinicios del FE (un bloqueo viejo en MAR 20-22 / VIE 19-22 descarta la 753 → queda 1). Pendiente: que Carlos limpie ese localStorage o pase payload/response reales de Network.

**Vacíos / inexistentes:** No hay dominios de `auth`, `admin`, `professors/reviews`. `ocr/process-image` ya existe (US-01/02), usa **Gemini multimodal** (sin Cloud Vision) y fue **verificado end-to-end contra Gemini real** con una imagen de `test_images/` (los tests automatizados mockean el estructurador para no gastar cuota; falta un test de integración real automatizado). El dominio `schedules/` ya expone **`generate`** (US-07), pero `models.py` siguen siendo dataclasses (sin SQLAlchemy) y **no existe `SavedSchedule`** ni endpoints `schedules/saved` (US-09). Las conversaciones de chat existen pero **in-memory** (`app/domains/chat/store.py`), aún sin modelos SQLAlchemy ni persistencia. `db/migrations/versions/` solo tiene `.gitkeep` y `env.py` no importa modelos. `python-jose` y `passlib[bcrypt]` ya están en `pyproject.toml` pero sin código de auth.

### Estado del frontend (capa de datos)

- **Sin infraestructura compartida:** no hay `lib/http`, `apiClient`, axios, SWR ni React Query. Cada feature resuelve (o simula) su red por su cuenta.
- **Auth 100% mock:** `features/auth/loginAction.ts` valida contra `features/auth/testCredentials.ts` (cuentas fijas: `alumno@ulima.edu.pe / Alumno123`, `admin@ulima.edu.pe / Admin1234`). La sesión se guarda en `localStorage['smartsched.session']` = `{ user: { id, email, name, role }, expiresAt }`. `AuthGuard.tsx` solo lee ese localStorage client-side (sin validación en backend). Sin JWT, sin Google login.
- **OCR conectado:** `features/schedule-generator/extractCoursesFromFile.ts` → `POST {NEXT_PUBLIC_API_URL}/api/v1/ocr/process-image` (FormData campo `files`). **Ya no hay fallback** a `ocr_clean_output_example.json`: ante error (imagen ilegible 422, backend caído) muestra el mensaje real. Solo acepta imágenes (PDF fuera).
- **Generación de horarios:** YA conectada — `generateSchedules.ts` (server action) hace `fetch` a `POST /api/v1/schedules/generate`. El backtracking en JS fue eliminado.

> **🔄 Reconciliación de backlog (2026-05-31).** Carlos entregó el backlog oficial: **26 historias en 3 sprints**. Cambios vs. lo que documentaba este archivo:
> - **10 historias NUEVAS** agregadas (abajo, en sus sprints): **US-10** descargar horario, **US-11** generar nuevo horario (Sprint 2); **US-26** modificar perfil, **US-28** configurar plataforma (Sprint 1); **US-13** guardar conversaciones, **US-14** eliminar conversaciones, **US-15** reputación profesor, **US-16** dificultad de curso, **US-17** prerrequisitos, **US-18** cursos por nivel (**Sprint 3, NUEVO**).
> - 🤖 **Las consultas del Sprint 3 (US-15 reputación, US-16 dificultad, US-17 prerrequisitos, US-18 cursos por nivel) se resuelven vía el AGENTE IA** (conocimiento del LLM), **NO** vía una sección de profesores/cursos con DB. **(Aclaración de Carlos 2026-05-31.)** Por ahora **NO** se construye `features/professors` con datos reales ni los modelos `Professor`/`Review`/`Course` para estas; el trabajo es **reforzar el prompt/herramientas del agente** (extiende US-12). Las tablas siguen *diseñadas* en `docs/DATA_MODEL.md` por si más adelante se quiere data-driven.
> - ⚠️ **US-21 "Agregar Reseñas"** NO está en el backlog oficial y **pertenece al agente IA** (Carlos 2026-05-31): **no requiere la sección de profesores aún**. Se trata como parte del dominio de chat (US-12), no como módulo aparte.
> - **US-05 y US-06 movidas a Sprint 1** en el backlog oficial (aquí siguen físicamente bajo "SPRINT 02" por orden histórico; cada una tiene la nota).

### Matriz de historias — ¿qué es "funcional" hoy?

Dos sentidos distintos. **Conectado FE↔BE: US-01, US-02, US-07, US-12 y US-24 (login, vivo 2026-05-31)** (el resto sigue mock o pendiente). "Funciona en UI" = la pantalla opera de forma autónoma (estado cliente o mock).

| US | Frontend hoy | Backend hoy | Conectado | Qué falta |
|---|---|---|---|---|
| US-01 Subir imagen (OCR) | UI completa; fetch real, **sin fallback** (muestra el error) | ✅ `/ocr/process-image` (imágenes inline, sin GCS; **Gemini multimodal**, verificado real) | 🟢 **SÍ** | calidad del mapeo en grillas densas; test de integración real automatizado |
| US-02 Subir otra imagen | merge en estado cliente (dedupe código+sección) | ✅ acepta múltiples `files` por llamada | 🟢 **SÍ** (vía OCR) | — |
| US-03 Añadir manual | estado cliente | n/a | ✅ FE puro | no requiere backend |
| US-04 Eliminar fila | estado cliente | n/a | ✅ FE puro | no requiere backend |
| US-05 Editar fila | estado cliente | n/a | ✅ FE puro | no requiere backend |
| US-06 Horas no disponibles | grid en estado cliente | n/a | ✅ FE puro | enviar bloques al generador |
| US-07 Generar combinaciones | vía backend (`generateSchedules.ts` hace fetch; ya no genera en JS) | ✅ `POST /schedules/generate` (reúsa generador, timeout/límite/truncated) | 🟢 **SÍ** (verificado en vivo) | falta: auth para guardar (US-09); click-through del UI corriendo |
| US-08 Visualizar horarios | navegación cliente | n/a | ✅ FE puro | no requiere backend |
| US-09 Guardar horario | ✅ botón "Guardar" real (modal nombrar) + "Mis horarios" real (listar/ver/eliminar) | ✅ `POST/GET/GET{id}/DELETE /schedules/saved` (🔒, tope 10) **vivo en Neon** | 🟢 **SÍ (vivo 2026-05-31)** por API | prueba manual en navegador |
| US-10 Descargar horario | ❌ no hay descarga | n/a (o PDF server-side) | ❌ | exportar PDF/imagen en el FE (o endpoint de PDF) |
| US-11 Generar nuevo horario | ✅ "Crear nuevo"/"Finalizar" reinician el wizard (`reset`/`clearPersisted`) | n/a | 🟢 FE puro | prácticamente hecho; Carlos decidió NO confirmación destructiva |
| US-12 Chat IA | ✅ conectado (envía Bearer) | ✅ agente ADK in-process + **conversaciones persistidas en BD (protegido)** | 🟢 **SÍ (vivo en Neon 2026-06-01)** | falta: enviar mensaje desde navegador, CA-3 <3s, eval, deploy |
| US-13 Guardar conversaciones | ✅ lista/usa conversaciones (con token) | ✅ **persistido** (`chat/models.py` `Conversation`/`Message`, `user_id` FK, mig. 0010 aplicada) | 🟢 **SÍ (vivo en Neon 2026-06-01)** | prueba manual de enviar mensaje en navegador |
| US-14 Eliminar conversaciones | ✅ papelera para eliminar | ✅ `DELETE /chat/conversations/{id}` **persistido + valida ownership (404)** | 🟢 **SÍ (vivo en Neon 2026-06-01)** | confirmación destructiva (decisión FE) |
| US-15 Consultar reputación profesor 🤖 | vía **agente IA** (chat) | 🟡 agente IA (US-12) responde del LLM | 🟡 (vía chat) | reforzar el prompt del agente; **NO** requiere sección de profesores ni tablas `Professor`/`Review` aún |
| US-16 Consultar dificultad de curso 🤖 | vía **agente IA** (chat) | 🟡 agente IA responde del LLM | 🟡 (vía chat) | reforzar prompt; sin DB de cursos aún |
| US-17 Consultar prerrequisitos 🤖 | vía **agente IA** (chat) | 🟡 agente IA responde del LLM | 🟡 (vía chat) | reforzar prompt; sin tabla `course_prerequisites` aún |
| US-18 Consultar cursos por nivel 🤖 | vía **agente IA** (chat) | 🟡 agente IA responde del LLM | 🟡 (vía chat) | reforzar prompt; sin DB de cursos aún |
| US-21 Agregar reseñas 🤖 *(no en backlog oficial; es del agente IA)* | vía **agente IA** (chat) | 🟡 agente IA | 🟡 (vía chat) | **NO requiere sección de profesores aún** (aclaración Carlos 2026-05-31) |
| US-24 Iniciar sesión | ✅ cableado (`loginAction` real + redirección/guardia por rol) | ✅ `POST /auth/login` (bloqueo 3/15min) + `/auth/me` + `get_current_user`/`require_role` | 🟢 **SÍ (vivo, 2026-05-31)** por API | falta prueba manual desde el navegador; Google login (CA-3) diferido |
| US-25 Restablecer contraseña | mock (muta credenciales en memoria) | ❌ no existe | ❌ | tokens + email |
| US-26 Modificar perfil | mock (`features/profile`) | ❌ solo `/auth/me` (lectura) | ❌ | `PATCH /users/me` + cablear FE |
| US-28 Configurar plataforma | mock (`features/settings`) | ❌ no existe | ❌ | decidir si server-side (`preferences` JSONB) o solo cliente |
| US-29 Crear usuario (admin) | mock | ❌ no existe | ❌ | endpoint + `require_role` |
| US-30 Modificar usuario (admin) | mock | ❌ no existe | ❌ | endpoint + `require_role` |
| US-31 Eliminar usuario (admin) | mock | ❌ no existe | ❌ | endpoint + `require_role` |
| US-32 Crear cursos (admin) | mock (sin "publicar") | ❌ no existe | ❌ | modelos Course/Section + endpoints |
| (admin CRUD profesores) | mock | ❌ no existe | ❌ | sin US numerada; existe en el FE |

**Lectura rápida:** funcionan hoy en la UI por sí solas (FE puro, no necesitan backend) **US-03, US-04, US-05, US-06, US-08**; **US-01/02 (OCR) y US-07 (generación) ya van contra el backend**. Todo lo que implica **persistencia, auth o IA** (US-09, US-12, US-21, US-24, US-25, US-29–US-32) está mock y requiere construir el backend desde cero.

### Lo que falta para conectar (trabajo transversal)

1. **Auth real (JWT).** Bloquea casi todo lo protegido. Modelo `User` SQLAlchemy + login/roles/bloqueo + `get_current_user` + `require_role("admin")`.
2. **Persistencia.** Convertir las `dataclasses` de `users/` y `schedules/` en modelos SQLAlchemy, crear las **primeras migraciones Alembic** e importarlas en `app/db/migrations/env.py`.
3. **Cliente HTTP compartido en el FE.** Crear `src/lib/http/apiClient.ts` con base `NEXT_PUBLIC_API_URL` + header `Authorization`, y un contexto/manejo de sesión.
4. **Reemplazar las ~25 server actions mock** por llamadas reales y reemplazar el `AuthGuard` mock por validación contra el backend.
5. **Construir los routers faltantes:** `schedules/saved` (US-09), `auth`, `admin` (users + courses), `professors/reviews`. (Ya hechos: `ocr/process-image`, `schedules/generate`, `chat`.)
6. **Alinear contratos** (ver abajo) y **reemplazar el stub del agente IA** por la integración real en Vertex AI.

### Decisiones tomadas

- **(2026-05-28) Generación de horarios → backend.** ✅ **Implementado y conectado el 2026-05-29.** `POST /api/v1/schedules/generate` reutiliza `app/integrations/generator/generator.py`; el FE (`generateSchedules.ts`, server action) ya hace fetch y eliminó el backtracking en JS. Verificado en vivo (payload del FE → opciones correctas, bloqueos respetados). Implementa US-07: timeout 2 min, `MAX_OPTIONS=20`, flag `truncated`.
- **(2026-05-29) OCR → solo imágenes, procesamiento inline, SIN GCS.** El endpoint `/ocr/process-image` procesa los bytes inline — **no** se sube a GCS ni se soportan PDFs. Consecuencia: `/upload` y `bucket/` quedan como **piezas huérfanas** (no entran al flujo). Si en el futuro se necesitan PDFs, ahí se reintroduce GCS + batch async.
- **(2026-05-29) OCR → Gemini multimodal directo, SIN Cloud Vision.** El flujo previo (Vision `document_text_detection` → texto plano → Gemini solo-texto) **aplanaba la tabla 2D y perdía la relación fila×columna**: el modelo no sabía a qué día/sección pertenecía cada horario → días y horas mal asignados (verificado con `test_images/f3028cb3-…jpg`: los rangos `7-10` quedaban como un chorro sin estructura). Solución: pasar la **imagen directa** a `gemini-flash-latest` (es multimodal) vía `types.Part.from_bytes`; lee la grilla visualmente. El prompt entiende el formato real de ULIMA (rangos `7-10` por columna de día → `inicio/fin` HH:MM; aula solo si la celda la trae, si no `null`). `max_output_tokens=16384` para tablas densas. `service._merge_courses()` agrupa de forma determinista los cursos que el modelo a veces duplica (uno por sección). **`ocr/client.py` (Cloud Vision) + `scripts/ocr_smoke.py` quedan huérfanos** (se conservan por si se reintroduce). Smoke test del nuevo flujo: `uv run python scripts/ocr_smoke_multimodal.py <img>` (consume cuota real). Validado end-to-end: 3 cursos / 21 secciones correctos; residuos solo por calidad de imagen (dígitos 6/8 ambiguos en nº de sección).
- **(2026-05-30) Estrategia de sesión/token → DECIDIDO: `Bearer` + localStorage.** El FE guarda el JWT en `localStorage['smartsched.session']` y lo envía en `Authorization: Bearer`. Se descartó cookie HttpOnly (menos cambios sobre lo actual). El backend emite el token en `POST /auth/login` (HS256, 8 h).
- **(2026-05-30) Proveedor de BD → Neon** (Postgres serverless gratis, escala a cero) en vez de Cloud SQL (costo). ⚠️ Fuera de GCP — excepción solo para la BD. Código Postgres puro → solo cambia `DATABASE_URL`; `app/db/url.py` maneja SSL/limpieza/normalización de la URL. **(2026-05-31) Conectado y operativo:** proyecto Neon en `us-east-1` (Postgres 17.10), migraciones+seed+login verificados en vivo. `DATABASE_URL` real vive en `.env` (no commiteado).
- **(2026-05-30) Modelo de datos completo** en [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md): ER Mermaid + 11 tablas. `section_times` normalizada, prereqs M2M, JSONB solo para `saved_schedules`, profesor ≠ usuario, ids UUID string, rol canónico `student/admin`.

### Contratos a respetar al construir el backend

> 📄 **Detalle completo en [`CONTRACTS.md`](./CONTRACTS.md)** — tabla endpoint por endpoint (método, ruta, request/response exactos, validaciones Zod y mismatches) derivada del código real del frontend. Es el blueprint para construir el backend.


- **OCR:** el FE hace `POST {NEXT_PUBLIC_API_URL}/api/v1/ocr/process-image` con FormData campo `files` (múltiple) y espera
  `{ "cursos": [ { codigo, nombre, creditos, nivel, secciones: [ { seccion, profesor, vacantes, horario: [ { dia, inicio, fin, aula } ] } ] } ] }`.
  **Implementado (2026-05-29):** solo imágenes (`image/png`, `image/jpeg`, `image/webp`, ≤10 MB), procesadas **inline con Gemini multimodal** — la imagen va directa al modelo con `response_schema` (sin GCS, sin Cloud Vision, sin PDF). ⚠️ **Mismatch de nombre:** el backlog de US-01 dice `/ocr/extract`, pero el FE ya llama a `/ocr/process-image` → se implementó el del FE.
- **Sesión:** el FE actual usa `localStorage['smartsched.session'] = { user: { id, email, name, role }, expiresAt }`. El backend de auth deberá producir algo compatible o el FE deberá adaptarse cuando se decida la estrategia de token.

### Roadmap de conexión por fases (propuesto, sin implementar aún)

- **Fase 0 — Fundaciones:** modelos SQLAlchemy + Alembic base · auth (login/JWT/roles/bloqueo, US-24/25) · cliente HTTP + sesión en el FE · `AuthGuard` real.
- **Fase 1 — Flujo core del generador:** ✅ OCR (Gemini multimodal → `{cursos}`) · ✅ `POST /schedules/generate` · ✅ wizard conectado (US-01/02/06/07/08). **Falta:** guardar horarios (modelo + CRUD, US-09, bloqueado por auth).
- **Fase 2 — Resto:** chat real + conversaciones (US-12/13/14) · **consultas vía agente IA** (US-15/16/17/18 + US-21 reseñas — todo por el chat, sin sección de profesores) · admin usuarios/cursos (US-29–US-32, con "publicar") · perfil/settings (US-26/28) · descargar/nuevo horario (US-10/11).

---

## Convenciones generales

- **Idioma de commits**: español. Formato: `<tipo>(<alcance>): descripción breve`. Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Ejemplo: `feat(ocr): agregar endpoint de procesamiento de imagen`.
- **Naming backend**: snake_case para Python (variables, funciones, archivos). Schemas Pydantic en PascalCase.
- **Naming frontend**: camelCase para variables/funciones, PascalCase para componentes React, kebab-case para carpetas de features.
- **Tests obligatorios**: toda funcionalidad nueva debe tener tests unitarios y de integración.
- **Cobertura mínima**: >= 80% en backend (`uv run pytest --cov=app`).
- **Seguridad**: cero vulnerabilidades High antes de merge a main.
- **Ruff**: line-length 100, reglas E, F, I, N, UP, B, SIM, RUF.
- **pytest**: `asyncio_mode = "auto"` — funciones async no necesitan decorador.
- **Clientes GCP** (`vision.ImageAnnotatorClient`, `storage.Client`): cacheados con `@lru_cache`. En tests llamar `_get_client.cache_clear()` antes de patchear.

---

## Historias de Usuario

---

### SPRINT 01

---

## US-01 — Subir imagen

**Sprint:** 01

### Criterios de aceptación

1. DADO un estudiante en "Generador Horario", CUANDO arrastra y suelta una imagen/screenshot de cursos, ENTONCES el sistema muestra "Cursos Detectados" con tabla por profesor y hora.
2. DADO un estudiante, CUANDO arrastra una imagen borrosa, ENTONCES el sistema notifica "Error al procesar. Intente nuevamente".

### Tareas técnicas — Backend

- Endpoint `POST /api/v1/ocr/extract` que reciba imagen (multipart), la suba a GCS, ejecute OCR con Cloud Vision, extraiga texto, lo envíe al agente LLM para estructurar, y devuelva JSON `{"cursos": [...]}`.
- Schema de respuesta `OCRExtractionResponse` en `app/domains/schedules/schemas.py` o nuevo módulo `app/integrations/ocr/schemas.py`.
- Validación de tipo de archivo (solo imágenes: jpg, png, webp) y tamaño máximo (10 MB).
- Manejo de errores de Cloud Vision: capturar imágenes ilegibles/borrosas y devolver HTTP 422 con mensaje "Error al procesar. Intente nuevamente".
- Tests unitarios para el endpoint (mock de Cloud Vision).
- Test de integración con imagen de ejemplo en `app/integrations/ocr/test_images/`.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- En `src/features/schedule-generator/`: componente de drag-and-drop / selector de archivo en la página `/generator`.
- Llamada al endpoint `POST /api/v1/ocr/extract` desde `extractCoursesFromFile.ts`.
- Renderizar tabla "Cursos Detectados" con columnas: curso, sección, profesor, horario.
- Estado de carga (spinner/skeleton) mientras se procesa.
- Notificación de error si la imagen es borrosa (toast o alert con "Error al procesar. Intente nuevamente").
- Validación client-side de tipo de archivo y tamaño antes de enviar.

### Checklist

- [ ] **Back**: endpoint `POST /api/v1/ocr/extract` implementado
- [ ] **Back**: validación de tipo y tamaño de archivo
- [ ] **Back**: manejo de error por imagen borrosa (HTTP 422)
- [ ] **Back**: tests unitarios del endpoint OCR
- [ ] **Back**: test de integración con imagen de ejemplo
- [ ] **Front**: componente drag-and-drop en `/generator`
- [ ] **Front**: integración con endpoint OCR
- [ ] **Front**: tabla "Cursos Detectados" renderiza correctamente
- [ ] **Front**: estado de carga mientras se procesa
- [ ] **Front**: notificación de error por imagen borrosa
- [ ] **Validación manual**: CA-1 — arrastrar imagen válida → tabla con cursos
- [ ] **Validación manual**: CA-2 — arrastrar imagen borrosa → notificación de error
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- El endpoint devuelve la lista de cursos detectados en formato JSON. La tabla los renderiza correctamente en el frontend. Las imágenes borrosas muestran error descriptivo. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-02 — Subir otra imagen

**Sprint:** 01

### Criterios de aceptación

1. DADO un estudiante en "Cursos Detectados", CUANDO presiona "Agregar Imagen", ENTONCES puede subir otro screenshot y la tabla se actualiza (merge de cursos).
2. DADO un estudiante, CUANDO presiona "Agregar Imagen" y cancela el selector, ENTONCES la tabla no cambia y se notifica "Cancelado".

### Tareas técnicas — Backend

- El endpoint `POST /api/v1/ocr/extract` ya existe (US-01). Asegurar que la respuesta sea mergeable: el frontend acumula cursos de múltiples llamadas.
- Alternativa: endpoint `POST /api/v1/ocr/extract-merge` que reciba los cursos existentes + nueva imagen y devuelva la lista unificada (deduplicando por curso+sección).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Botón "Agregar Imagen" visible en la vista "Cursos Detectados".
- Al presionar, abrir selector de archivo (input file o drag-and-drop modal).
- Si el usuario selecciona archivo: enviar al endpoint OCR, mergear nuevos cursos con los existentes en el state de `useScheduleWizard`.
- Si el usuario cancela el selector: detectar evento de cancelación, mostrar toast "Cancelado", tabla intacta.
- Evitar duplicados en la tabla al mergear.

### Checklist

- [ ] **Back**: endpoint soporta múltiples invocaciones (respuesta mergeable)
- [ ] **Back**: tests de merge / deduplicación
- [ ] **Front**: botón "Agregar Imagen" en vista Cursos Detectados
- [ ] **Front**: lógica de merge de cursos en state
- [ ] **Front**: manejo de cancelación del selector de archivo
- [ ] **Front**: toast "Cancelado" al cancelar
- [ ] **Validación manual**: CA-1 — agregar segunda imagen → tabla actualizada con cursos mergeados
- [ ] **Validación manual**: CA-2 — cancelar selector → tabla intacta + notificación "Cancelado"
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- El usuario puede agregar múltiples imágenes y la tabla acumula cursos sin duplicados. Cancelar el selector no modifica la tabla. Tests pasan. Sin vulnerabilidades High.

---

## US-03 — Añadir manualmente

**Sprint:** 01

### Criterios de aceptación

1. DADO un estudiante en "Cursos Detectados", CUANDO visualiza una ausencia y presiona "+ Añadir Curso", ENTONCES puede añadir el curso al final de la tabla.
2. DADO un estudiante, CUANDO presiona "+ Añadir Curso" y deja información incompleta, ENTONCES el campo se pone en rojo con "Este campo es requerido".

### Tareas técnicas — Backend

- No requiere endpoint nuevo si la tabla es solo estado del frontend previo a la generación. Si se persiste server-side, crear `POST /api/v1/schedules/courses` para guardar cursos manuales.
- Validación de schema: todos los campos obligatorios (nombre, sección, profesor, horario).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Botón "+ Añadir Curso" al final de la tabla de Cursos Detectados.
- Al presionar: añadir fila editable vacía al final de la tabla (inline form o modal).
- Campos: nombre del curso, sección, profesor, día(s), hora inicio, hora fin.
- Validación con Zod: campos requeridos. Campo vacío → borde rojo + texto "Este campo es requerido".
- Al confirmar, añadir al state de cursos en `useScheduleWizard`.
- Botón cancelar descarta la fila vacía sin cambios.

### Checklist

- [ ] **Back**: validación de schema para curso manual (si aplica)
- [ ] **Front**: botón "+ Añadir Curso" en la tabla
- [ ] **Front**: fila editable con campos del curso
- [ ] **Front**: validación Zod — campos vacíos en rojo con "Este campo es requerido"
- [ ] **Front**: curso añadido aparece al final de la tabla
- [ ] **Front**: cancelar descarta sin cambios
- [ ] **Validación manual**: CA-1 — añadir curso completo → aparece al final de la tabla
- [ ] **Validación manual**: CA-2 — dejar campo vacío → borde rojo + "Este campo es requerido"
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- El estudiante puede añadir cursos manualmente a la tabla. Los campos incompletos se validan visualmente con mensaje claro. Tests pasan. Sin vulnerabilidades High.

---

## US-04 — Eliminar fila

**Sprint:** 01

### Criterios de aceptación

1. DADO un estudiante en "Cursos Detectados", CUANDO selecciona cursos mal generados y presiona "Eliminar", ENTONCES desaparecen y se notifica "Curso Eliminado".
2. DADO un estudiante sin conexión, CUANDO presiona "Eliminar", ENTONCES falla y notifica "Error de Conexión".

### Tareas técnicas — Backend

- Si la tabla es solo estado frontend, no requiere endpoint. Si hay persistencia server-side, crear `DELETE /api/v1/schedules/courses/{id}` o batch delete `POST /api/v1/schedules/courses/delete` con lista de IDs.
- Devolver HTTP 200 con confirmación o HTTP 503 si hay problema de conectividad.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Checkboxes o selección múltiple en cada fila de la tabla.
- Botón "Eliminar" habilitado solo si hay filas seleccionadas.
- Al eliminar: remover del state, mostrar toast "Curso Eliminado".
- Detección de sin conexión (`navigator.onLine` o catch de fetch): mostrar toast "Error de Conexión".
- Considerar confirmación antes de eliminar (modal "¿Estás seguro?").

### Checklist

- [ ] **Back**: endpoint de eliminación (si aplica persistencia server-side)
- [ ] **Front**: selección múltiple en la tabla
- [ ] **Front**: botón "Eliminar" condicionado a selección
- [ ] **Front**: eliminación del state + toast "Curso Eliminado"
- [ ] **Front**: detección offline + toast "Error de Conexión"
- [ ] **Validación manual**: CA-1 — seleccionar y eliminar → cursos desaparecen + notificación
- [ ] **Validación manual**: CA-2 — sin conexión + eliminar → notificación "Error de Conexión"
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Cursos seleccionados se eliminan de la tabla con notificación. El estado offline muestra error descriptivo. Tests pasan. Sin vulnerabilidades High.

---

## US-24 — Iniciar Sesión

**Sprint:** 01

### Criterios de aceptación

1. DADO un estudiante o admin en "BIENVENIDO ULIMEÑO", CUANDO ingresa credenciales válidas, ENTONCES entra a su cuenta con las limitaciones de su rol.
2. DADO credenciales inválidas, ENTONCES tiene 3 intentos y si falla los 3 se bloquea por 15 minutos.
3. DADO un estudiante, CUANDO inicia sesión con Google y es válida, ENTONCES ingresa a sus funcionalidades.

### Tareas técnicas — Backend

- Endpoint `POST /api/v1/auth/login` con email + password. Devolver JWT (access token + refresh token) con campo `role` ("estudiante" | "admin").
- Modelo `User` en DB con campos: id, email, password_hash, role, failed_attempts, locked_until.
- Migración Alembic para tabla `users`.
- Lógica de bloqueo: incrementar `failed_attempts` en cada intento fallido. Si `failed_attempts >= 3`, setear `locked_until = now + 15 min`. Rechazar login si `locked_until > now` con HTTP 423.
- Endpoint `POST /api/v1/auth/google` para login con Google (verificar ID token de Google, crear/buscar usuario, devolver JWT).
- Middleware o dependency de autenticación: `get_current_user` que valide el JWT en header `Authorization: Bearer <token>`.
- Dependency `require_role("admin")` para proteger endpoints de admin.
- Hash de passwords con passlib/bcrypt (ya en dependencias).
- Tests: login exitoso, credenciales inválidas, bloqueo tras 3 intentos, desbloqueo tras 15 min, login Google.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Página `/login` ya existe en `src/app/(public)/login/page.tsx` y `src/features/auth/`.
- Conectar `LoginForm.tsx` al endpoint real `POST /api/v1/auth/login`.
- Almacenar JWT (cookie HttpOnly o localStorage) y role del usuario.
- Redirigir según rol: estudiante → `/inicio`, admin → `/admin/accounts`.
- Mostrar contador de intentos restantes si falla: "X intentos restantes".
- Mostrar mensaje de bloqueo: "Cuenta bloqueada. Intente en 15 minutos".
- Botón "Iniciar sesión con Google": integrar Google Sign-In, enviar ID token al backend.
- Proteger rutas `(protected)` verificando JWT válido; redirigir a `/login` si no autenticado.

### Checklist

- [ ] **Back**: modelo User con campos auth (password_hash, failed_attempts, locked_until, role)
- [ ] **Back**: migración Alembic para tabla users
- [ ] **Back**: endpoint `POST /api/v1/auth/login`
- [ ] **Back**: lógica de bloqueo tras 3 intentos (15 min)
- [ ] **Back**: endpoint `POST /api/v1/auth/google`
- [ ] **Back**: dependency `get_current_user` (JWT validation)
- [ ] **Back**: dependency `require_role("admin")`
- [ ] **Back**: tests unitarios auth (login, bloqueo, google)
- [ ] **Back**: tests de integración auth
- [ ] **Front**: conectar LoginForm al endpoint real
- [ ] **Front**: almacenamiento de JWT y role
- [ ] **Front**: redirección por rol post-login
- [ ] **Front**: mensaje de intentos restantes / bloqueo
- [ ] **Front**: integración Google Sign-In
- [ ] **Front**: protección de rutas (protected) con JWT
- [ ] **Validación manual**: CA-1 — credenciales válidas → entra según rol
- [ ] **Validación manual**: CA-2 — 3 intentos fallidos → bloqueo 15 min
- [ ] **Validación manual**: CA-3 — Google login válido → entra a funcionalidades
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Login con email/password y Google funcional. Roles aplican correctamente. Bloqueo tras 3 intentos por 15 minutos verificado. JWT protege rutas. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-25 — Restablecer Contraseña

**Sprint:** 01

### Criterios de aceptación

1. DADO un estudiante en "BIENVENIDO ULIMEÑO", CUANDO presiona "¿Olvidaste tu contraseña?" e ingresa su correo, ENTONCES puede presionar "Enviar enlace" y restablecer.
2. DADO un estudiante que se equivoca al entrar al flujo, CUANDO presiona "Cancelar", ENTONCES regresa a la pantalla inicial.

### Tareas técnicas — Backend

- Endpoint `POST /api/v1/auth/forgot-password` con email. Generar token temporal (UUID + expiración 1h), guardarlo en DB o cache. Enviar email con enlace de restablecimiento.
- Endpoint `POST /api/v1/auth/reset-password` con token + nueva contraseña. Validar token, hashear nueva contraseña, actualizar en DB, invalidar token.
- Integración con servicio de email (SendGrid, GCP SMTP, o similar).
- Validación: email debe existir en DB (no revelar si existe o no por seguridad — devolver siempre 200).
- Tests: flujo completo de reset, token expirado, token inválido.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- En `/login`: link "¿Olvidaste tu contraseña?" que muestra formulario/modal con campo email.
- Botón "Enviar enlace" → `POST /api/v1/auth/forgot-password`. Mostrar "Enlace enviado a tu correo".
- Botón "Cancelar" → volver a la pantalla de login sin cambios.
- Página `/reset-password?token=xxx` con formulario de nueva contraseña + confirmación.
- Validación Zod: contraseña mínima 8 chars, coincidencia de confirmación.
- Schema ya existe en `src/features/settings/resetPassword.schema.ts` — reutilizar o adaptar.

### Checklist

- [ ] **Back**: endpoint `POST /api/v1/auth/forgot-password`
- [ ] **Back**: endpoint `POST /api/v1/auth/reset-password`
- [ ] **Back**: generación y validación de token temporal
- [ ] **Back**: integración con servicio de email
- [ ] **Back**: tests (flujo completo, token expirado, token inválido)
- [ ] **Front**: link "¿Olvidaste tu contraseña?" en login
- [ ] **Front**: formulario de email + botón "Enviar enlace"
- [ ] **Front**: botón "Cancelar" vuelve a login
- [ ] **Front**: página de reset con nueva contraseña + confirmación
- [ ] **Front**: validación Zod de contraseña
- [ ] **Validación manual**: CA-1 — ingresar correo → recibir enlace → restablecer contraseña
- [ ] **Validación manual**: CA-2 — presionar "Cancelar" → volver a pantalla de login
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Flujo completo de restablecimiento funcional: solicitar enlace, recibir email, cambiar contraseña. Cancelar regresa al login. Tests pasan. Sin vulnerabilidades High.

---

## US-26 — Modificar perfil

**Sprint:** 01 · **Nueva (backlog oficial 2026-05-31)**

### Criterios de aceptación

1. DADO un estudiante en su perfil, CUANDO edita sus datos básicos y guarda, ENTONCES el sistema valida la información y persiste los cambios.
2. DADO un dato inválido (p. ej. nombre vacío), CUANDO intenta guardar, ENTONCES se muestra el error y no se guarda.

### Tareas técnicas — Backend

- Endpoint `PATCH /api/v1/users/me` (protegido con `get_current_user`) para actualizar campos básicos del usuario (p. ej. `name`; el email/rol no se editan desde aquí). `GET /api/v1/auth/me` ya devuelve el perfil.
- Schema `UserUpdate` (Pydantic) con validación; reusar `UserOut` para la respuesta.
- Tests: actualización OK, validación, 401 sin token.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- `features/profile` ya existe (mock). Cablear el formulario a `PATCH /api/v1/users/me` (con `getToken()`), refrescar la sesión local tras guardar.
- Validación Zod de campos; estado de carga + toast de confirmación.

### Estado actual

FE mock (`features/profile`); BE solo expone lectura (`/auth/me`). Falta el `PATCH` y el cableado.

### Definition of Done

- El estudiante edita y guarda su perfil; cambios validados y persistidos en Neon. Tests pasan. Sin vulnerabilidades High.

---

## US-28 — Configurar plataforma

**Sprint:** 01 · **Nueva (backlog oficial 2026-05-31)**

### Criterios de aceptación

1. DADO un estudiante en "Configuración", CUANDO modifica preferencias básicas, ENTONCES el sistema conserva la configuración y la refleja en la interfaz.

### Tareas técnicas — Backend

- **Decisión pendiente:** si las preferencias son solo de UI (tema, densidad, etc.) pueden vivir **solo en el cliente** (localStorage) y NO requerir backend. Si deben sincronizarse entre dispositivos, agregar `preferences` (JSONB) en `users` o tabla `user_preferences` + `PATCH /api/v1/users/me/preferences`.
- Tests si se implementa server-side.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- `features/settings` ya existe (mock). Persistir preferencias (cliente o vía endpoint según la decisión) y reflejarlas en la UI.

### Estado actual

FE mock (`features/settings`); BE no existe. Definir primero si necesita persistencia server-side.

### Definition of Done

- Las preferencias se conservan y se reflejan en la UI. Si hay backend, tests pasan. Sin vulnerabilidades High.

---

### SPRINT 02

---

## US-05 — Editar fila

**Sprint:** 02 → reasignada a **Sprint 1** en el backlog oficial (2026-05-31)

### Criterios de aceptación

1. DADO un estudiante en "Cursos Detectados", CUANDO selecciona un curso y le da "Editar", ENTONCES puede cambiar la información y la tabla se actualiza al instante.
2. DADO un estudiante editando, CUANDO pulsa "ESC", ENTONCES descarta cambios y la tabla vuelve al estado anterior.

### Tareas técnicas — Backend

- Si la tabla es estado frontend, no requiere endpoint. Si hay persistencia: `PUT /api/v1/schedules/courses/{id}` con schema de actualización parcial.
- Validación de schema: mismos campos que creación.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Botón "Editar" en cada fila de la tabla de Cursos Detectados.
- Al presionar: la fila se convierte en inputs editables (inline editing).
- Guardar estado anterior para rollback.
- Al confirmar (Enter o botón guardar): actualizar state y tabla al instante.
- Al presionar ESC: descartar cambios, restaurar estado anterior.
- Listener de teclado para ESC en el componente de edición.

### Checklist

- [ ] **Back**: endpoint de edición (si aplica persistencia)
- [ ] **Front**: botón "Editar" por fila
- [ ] **Front**: modo de edición inline con inputs
- [ ] **Front**: guardar estado anterior para rollback
- [ ] **Front**: confirmar → actualización inmediata
- [ ] **Front**: ESC → descarta cambios
- [ ] **Validación manual**: CA-1 — editar curso → tabla actualizada al instante
- [ ] **Validación manual**: CA-2 — pulsar ESC → cambios descartados
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Edición inline funcional con actualización instantánea. ESC descarta cambios. Tests pasan. Sin vulnerabilidades High.

---

## US-06 — Editar Horas de no trabajo

**Sprint:** 02 → reasignada a **Sprint 1** en el backlog oficial (2026-05-31)

### Criterios de aceptación

1. DADO un estudiante en "Horas No Disponibles", CUANDO selecciona un cuadro de hora y se pinta naranja, ENTONCES el sistema bloquea esas horas para generar horarios.
2. DADO una hora ya seleccionada, CUANDO le da click al cuadro coloreado, ENTONCES se desbloquea.

### Tareas técnicas — Backend

- Las horas no disponibles se envían como `unavailable: [TimeBlock]` al llamar al generador. No requiere persistencia inmediata a menos que se quieran guardar preferencias del usuario.
- Si se persiste: `PUT /api/v1/schedules/unavailable` con lista de bloques `{day, start, end}`.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Componente grilla semanal (Lun-Sáb, 7:00-22:00 en intervalos de 1h) en el paso "Horas No Disponibles" del wizard.
- Click en celda → toggle: sin color → naranja (bloqueado). Naranja → sin color (desbloqueado).
- State: lista de `{day: number, start: string, end: string}` que se envía al backend al generar.
- Soporte para click-and-drag para seleccionar rangos.
- Visual: naranja para bloqueado, blanco/gris para disponible.

### Checklist

- [ ] **Back**: aceptar `unavailable` blocks en el endpoint de generación
- [ ] **Front**: grilla semanal interactiva
- [ ] **Front**: toggle click: seleccionar (naranja) / deseleccionar
- [ ] **Front**: state de bloques no disponibles
- [ ] **Front**: visual claro de estados
- [ ] **Validación manual**: CA-1 — click en celda → se pinta naranja
- [ ] **Validación manual**: CA-2 — click en celda naranja → se desbloquea
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Grilla interactiva funcional con toggle de horas. Los bloques se transmiten al generador. Tests pasan. Sin vulnerabilidades High.

---

## US-07 — Generar combinaciones

**Sprint:** 02

### Criterios de aceptación

1. DADO un estudiante en "Horas No Disponibles", CUANDO termina y presiona "Generar", ENTONCES el sistema procesa la solicitud y espera hasta 2 minutos a que se generen las combinaciones.
2. DADO restricciones imposibles, CUANDO presiona "Generar", ENTONCES no encuentra combinaciones y debe modificar selecciones.

### Tareas técnicas — Backend

- Endpoint `POST /api/v1/schedules/generate` que reciba `{sections: [...], unavailable: [...], target: int}` y devuelva lista de horarios generados.
- Usar `generate_schedules()` de `app/integrations/generator/generator.py`.
- Timeout de 2 minutos: si el backtracking excede el tiempo, devolver las combinaciones encontradas hasta ese punto o HTTP 408.
- Si no hay combinaciones posibles: devolver HTTP 200 con lista vacía y mensaje descriptivo.
- Limitar la cantidad de combinaciones devueltas (ej. máximo 50).
- Tests: generación exitosa, restricciones imposibles (0 resultados), timeout.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Botón "Generar" al final del paso "Horas No Disponibles".
- Al presionar: enviar cursos detectados + horas no disponibles al endpoint.
- Estado de carga con indicador de progreso o spinner ("Generando combinaciones...") con timeout visual de 2 min.
- Si hay resultados: navegar al paso "Horarios Generados".
- Si no hay resultados: mostrar mensaje "No se encontraron combinaciones. Modifique sus selecciones." y mantener al usuario en el paso actual.
- Integrar con `generateSchedules.ts` y `useScheduleWizard.ts`.

### Checklist

- [ ] **Back**: endpoint `POST /api/v1/schedules/generate`
- [ ] **Back**: integración con `generate_schedules()`
- [ ] **Back**: timeout de 2 minutos
- [ ] **Back**: respuesta vacía para restricciones imposibles
- [ ] **Back**: límite de combinaciones devueltas
- [ ] **Back**: tests (exitoso, imposible, timeout)
- [ ] **Front**: botón "Generar" conectado al endpoint
- [ ] **Front**: spinner / estado de carga con timeout visual
- [ ] **Front**: navegación a "Horarios Generados" con resultados
- [ ] **Front**: mensaje de "sin combinaciones" con opción de modificar
- [ ] **Validación manual**: CA-1 — generar con datos válidos → combinaciones en <= 2 min
- [ ] **Validación manual**: CA-2 — restricciones imposibles → mensaje de modificar selecciones
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Generación de combinaciones funcional con timeout de 2 min. Restricciones imposibles muestran mensaje claro. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-08 — Visualizar horarios

**Sprint:** 02

### Criterios de aceptación

1. DADO un estudiante en "Horarios Generados", CUANDO presiona "Anterior" o "Siguiente", ENTONCES el sistema desplaza horarios y muestra otra alternativa.
2. DADO un único horario, CUANDO presiona los botones, ENTONCES muestra el único disponible sin más selecciones.

### Tareas técnicas — Backend

- No requiere endpoint adicional: los horarios ya están en la respuesta de generación.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Vista "Horarios Generados": mostrar horario actual como grilla semanal coloreada (cada curso con color distinto).
- Botones "Anterior" y "Siguiente" para navegar entre combinaciones.
- Indicador de posición: "Horario X de Y".
- Si solo hay 1 horario: botones deshabilitados o ocultos, mostrar solo el horario.
- Navegación circular o con tope (primer/último).

### Checklist

- [ ] **Front**: vista de grilla semanal con horario coloreado por curso
- [ ] **Front**: botones "Anterior" / "Siguiente" funcionales
- [ ] **Front**: indicador "Horario X de Y"
- [ ] **Front**: botones deshabilitados si solo hay 1 horario
- [ ] **Validación manual**: CA-1 — navegar entre múltiples horarios
- [ ] **Validación manual**: CA-2 — un solo horario → botones no funcionales
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Navegación entre horarios generados funcional. Caso de horario único manejado correctamente. Tests pasan. Sin vulnerabilidades High.

---

## US-09 — Guardar Horario

**Sprint:** 02

### Criterios de aceptación

1. DADO un estudiante visualizando un horario, CUANDO presiona "Guardar", ENTONCES se abre modal para nombrar el horario y queda guardado en "Mis horarios" (hasta 10).

### Tareas técnicas — Backend

- Modelo `SavedSchedule` en DB: id, user_id (FK), name, schedule_data (JSONB), created_at.
- Migración Alembic.
- Endpoint `POST /api/v1/schedules/saved` — guardar horario con nombre. Validar límite de 10 por usuario.
- Endpoint `GET /api/v1/schedules/saved` — listar horarios guardados del usuario autenticado.
- Endpoint `DELETE /api/v1/schedules/saved/{id}` — eliminar horario guardado.
- Proteger con `get_current_user`.
- Tests: guardar, listar, eliminar, límite de 10.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Botón "Guardar" en la vista de horario generado.
- Modal con campo de texto para nombre del horario.
- Al confirmar: `POST /api/v1/schedules/saved`, toast "Horario guardado".
- Si ya tiene 10 horarios: mensaje "Límite alcanzado. Elimine un horario antes de guardar otro."
- Sección "Mis horarios" accesible desde el dashboard o navegación.
- Lista de horarios guardados con opción de ver y eliminar.

### Checklist

- [ ] **Back**: modelo `SavedSchedule` + migración Alembic
- [ ] **Back**: endpoint `POST /api/v1/schedules/saved`
- [ ] **Back**: endpoint `GET /api/v1/schedules/saved`
- [ ] **Back**: endpoint `DELETE /api/v1/schedules/saved/{id}`
- [ ] **Back**: validación límite de 10 horarios por usuario
- [ ] **Back**: protección con `get_current_user`
- [ ] **Back**: tests (guardar, listar, eliminar, límite)
- [ ] **Front**: botón "Guardar" en vista de horario
- [ ] **Front**: modal con nombre del horario
- [ ] **Front**: mensaje de límite alcanzado (10)
- [ ] **Front**: sección "Mis horarios" con lista
- [ ] **Front**: opciones de ver y eliminar horarios guardados
- [ ] **Validación manual**: CA-1 — guardar horario con nombre → aparece en "Mis horarios"
- [ ] **Validación manual**: verificar límite de 10 horarios
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Horarios se guardan con nombre, se listan y eliminan. Límite de 10 respetado. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-12 — Iniciar Nueva Conversación (Agente IA)

**Sprint:** 02

> **🟢 Estado 2026-05-29 — MVP funcional conectado FE↔BE (fase in-memory).**
> Hecho: agente ADK real in-process (proyecto `ulima-agent/`, `gemini-flash-latest`, proyecto GCP `ulima-agent`),
> endpoints `POST /chat` + `GET/POST/DELETE /chat/conversations` (in-memory), frontend `features/ai-agent`
> conectado (sin mocks, un solo botón "Nueva conversación", layout full-bleed, eliminar conversaciones,
> avatar servido en `/static/chatbot.png`). CA-1 ✅. Tests backend (`tests/test_chat.py`) + lint OK.
> **Pendiente DoD:** CA-2 (auth real → US-24), CA-3 (<3s sin medir), persistencia `Conversation`/`Message` + Alembic
> (hoy in-memory por decisión), eval del agente, deploy a Cloud Run, code review + merge a QA, commit.

### Criterios de aceptación

1. DADO un estudiante en "Agente IA", CUANDO pulsa "+ Nueva conversación", ENTONCES se genera un chat con box de pregunta y puede enviar consulta al agente.
2. DADO un usuario no logueado, CUANDO pulsa "+ Nueva conversación", ENTONCES el sistema pide iniciar sesión y no permite consultas.
3. Respuesta del agente IA en menos de 3 segundos.

### Tareas técnicas — Backend

- Reemplazar stub en `app/integrations/agent/ulima_agent.py` con integración real a Vertex AI Agent / ADK.
- El endpoint `POST /api/v1/chat` ya existe. Protegerlo con `get_current_user`.
- Crear/gestionar sesiones de chat: `session_id` ligado al usuario autenticado.
- Persistencia de conversaciones: modelo `Conversation` (id, user_id, title, created_at) y `Message` (id, conversation_id, role, content, created_at) en DB.
- Endpoint `GET /api/v1/chat/conversations` — listar conversaciones del usuario.
- Endpoint `POST /api/v1/chat/conversations` — crear nueva conversación.
- Optimizar para respuesta < 3 segundos: streaming si es posible, o timeout configurado.
- Tests: crear conversación, enviar mensaje, usuario no autenticado (401), rendimiento < 3s.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Página `/ai-agent` ya existe. Conectar a endpoints reales.
- Botón "+ Nueva conversación" → `POST /api/v1/chat/conversations`.
- Chat interface: caja de texto + envío → `POST /api/v1/chat` con `session_id`.
- Mostrar respuesta del agente en burbuja de chat.
- Si usuario no logueado: interceptar en middleware/layout y redirigir a login con mensaje "Inicia sesión para usar el Agente IA".
- Indicador de escritura ("El agente está pensando...") mientras espera respuesta.
- Sidebar con lista de conversaciones previas (`GET /api/v1/chat/conversations`).
- Hooks existentes: `useChat.ts`, `sendMessage.ts`, `getConversations.ts` — conectar a API real.

### Checklist

- [ ] **Back**: integración real con Vertex AI Agent (reemplazar stub)
- [ ] **Back**: proteger `POST /api/v1/chat` con `get_current_user`
- [ ] **Back**: modelo Conversation + Message + migración Alembic
- [ ] **Back**: endpoint `GET /api/v1/chat/conversations`
- [ ] **Back**: endpoint `POST /api/v1/chat/conversations`
- [ ] **Back**: optimización de respuesta < 3s
- [ ] **Back**: tests (conversación, mensaje, 401 no autenticado)
- [ ] **Front**: botón "+ Nueva conversación" conectado
- [ ] **Front**: chat interface con envío de mensajes
- [ ] **Front**: renderizado de respuesta del agente
- [ ] **Front**: redirección a login si no autenticado
- [ ] **Front**: indicador "El agente está pensando..."
- [ ] **Front**: sidebar con conversaciones previas
- [ ] **Validación manual**: CA-1 — nueva conversación + enviar pregunta → respuesta del agente
- [ ] **Validación manual**: CA-2 — usuario no logueado → redirigido a login
- [ ] **Validación manual**: CA-3 — respuesta en menos de 3 segundos
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Chat con agente IA funcional, protegido por autenticación. Conversaciones persistidas. Respuesta < 3 segundos. Usuario no logueado redirigido. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-21 — Agregar Reseñas

**Sprint:** 02 · 🤖 **Pertenece al AGENTE IA (Carlos 2026-05-31) — NO está en el backlog oficial**

> 🤖 **Aclaración Carlos 2026-05-31:** US-21 es del **agente IA** y **NO requiere la sección de profesores aún**. No se construye módulo de reseñas/profesores con DB; cualquier interacción de reseñas/reputación se canaliza por el chat (US-12). Las tareas técnicas REST de abajo quedan como referencia histórica (fuera de alcance actual). Ver también US-15.

### Criterios de aceptación

1. DADO un estudiante en "Consultar Profesores", CUANDO presiona "Ver Reseñas", ENTONCES ve las reseñas y puede añadir la suya redactando y pulsando "Publicar".
2. DADO un estudiante que no quiere reseñar, CUANDO pulsa "Cancelar", ENTONCES la información queda intacta.

### Tareas técnicas — Backend

- Modelo `Review` en DB: id, user_id (FK), professor_id (FK), content (text), rating (int 1-5), created_at.
- Modelo `Professor` en DB si no existe: id, name, department, etc.
- Migración Alembic.
- Endpoint `GET /api/v1/professors/{id}/reviews` — listar reseñas de un profesor.
- Endpoint `POST /api/v1/professors/{id}/reviews` — crear reseña (autenticado). Validar: content no vacío, rating 1-5, una reseña por usuario por profesor.
- Proteger con `get_current_user`.
- Tests: listar reseñas, crear reseña, duplicado (409), validación.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Página `/professors` ya existe con `src/features/professors/`.
- Botón "Ver Reseñas" por profesor → expande/abre panel o modal con lista de reseñas.
- Formulario para nueva reseña: textarea + selector de rating (estrellas) + botón "Publicar".
- Al publicar: `POST /api/v1/professors/{id}/reviews`, agregar reseña a la lista.
- Botón "Cancelar" cierra el formulario sin cambios.
- Schema de validación con Zod (`rating.schema.ts` ya existe — reutilizar/adaptar).

### Checklist

- [ ] **Back**: modelo Review + migración Alembic
- [ ] **Back**: modelo Professor en DB (si no existe)
- [ ] **Back**: endpoint `GET /api/v1/professors/{id}/reviews`
- [ ] **Back**: endpoint `POST /api/v1/professors/{id}/reviews`
- [ ] **Back**: validación (una reseña por usuario/profesor, rating 1-5)
- [ ] **Back**: protección con `get_current_user`
- [ ] **Back**: tests (listar, crear, duplicado, validación)
- [ ] **Front**: botón "Ver Reseñas" por profesor
- [ ] **Front**: lista de reseñas existentes
- [ ] **Front**: formulario nueva reseña (textarea + rating + "Publicar")
- [ ] **Front**: "Cancelar" cierra sin cambios
- [ ] **Validación manual**: CA-1 — ver reseñas + añadir nueva → aparece publicada
- [ ] **Validación manual**: CA-2 — cancelar → información intacta
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Reseñas de profesores visibles y publicables. Una reseña por usuario/profesor. Cancelar no modifica nada. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-29 — Crear usuario (admin)

**Sprint:** 02

### Criterios de aceptación

1. DADO un admin en "Gestión de Cuentas", CUANDO pulsa "+ Nuevo Usuario" y selecciona "Estudiante", ENTONCES completa formulario y "Agregar" crea al estudiante.
2. Igual flujo para crear "Admin".
3. En ambos casos, "Cancelar" descarta.

### Tareas técnicas — Backend

- Endpoint `POST /api/v1/admin/users` — crear usuario (estudiante o admin). Campos: name, email, password, role.
- Proteger con `require_role("admin")`.
- Hash de password antes de guardar.
- Validar email único.
- Devolver usuario creado (sin password).
- Tests: crear estudiante, crear admin, email duplicado (409), sin permiso (403).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Página `/admin/accounts` ya existe con `AddUserDialog.tsx`.
- Botón "+ Nuevo Usuario" → modal con selector de rol (Estudiante/Admin) y formulario.
- Campos: nombre, correo, contraseña.
- "Agregar" → `POST /api/v1/admin/users`, cerrar modal, refrescar lista.
- "Cancelar" → cerrar modal sin cambios.
- Validación Zod: email válido, contraseña mínima 8 chars, nombre no vacío.

### Checklist

- [ ] **Back**: endpoint `POST /api/v1/admin/users`
- [ ] **Back**: protección `require_role("admin")`
- [ ] **Back**: validación email único
- [ ] **Back**: hash de password
- [ ] **Back**: tests (crear estudiante, crear admin, duplicado, 403)
- [ ] **Front**: modal de creación con selector de rol
- [ ] **Front**: formulario con validación Zod
- [ ] **Front**: "Agregar" crea y refresca lista
- [ ] **Front**: "Cancelar" cierra sin cambios
- [ ] **Validación manual**: CA-1 — crear estudiante exitosamente
- [ ] **Validación manual**: CA-2 — crear admin exitosamente
- [ ] **Validación manual**: CA-3 — cancelar descarta sin cambios
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Admin puede crear usuarios de ambos roles. Email duplicado rechazado. Cancelar descarta. Tests pasan. Sin vulnerabilidades High.

---

## US-30 — Modificar usuario (admin)

**Sprint:** 02

### Criterios de aceptación

1. DADO un admin en "Gestión de Cuentas" viendo el listado, CUANDO pulsa el botón editar, ENTONCES puede modificar nombre, correo y otros aspectos del alumno.

### Tareas técnicas — Backend

- Endpoint `PUT /api/v1/admin/users/{id}` — actualizar usuario. Campos modificables: name, email, role. Password solo si se envía explícitamente.
- Proteger con `require_role("admin")`.
- Validar email único (excluyendo el propio usuario).
- Tests: editar nombre, editar email, email duplicado (409), sin permiso (403).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- `EditUserDialog.tsx` ya existe en `src/features/admin/accounts/components/`.
- Botón editar por fila → abre modal con datos pre-cargados.
- Campos editables: nombre, correo, rol.
- "Guardar" → `PUT /api/v1/admin/users/{id}`, cerrar modal, refrescar lista.
- "Cancelar" → cerrar sin cambios.

### Checklist

- [ ] **Back**: endpoint `PUT /api/v1/admin/users/{id}`
- [ ] **Back**: protección `require_role("admin")`
- [ ] **Back**: validación email único (excluyendo propio)
- [ ] **Back**: tests (editar, duplicado, 403)
- [ ] **Front**: modal de edición con datos pre-cargados
- [ ] **Front**: guardar → actualiza y refresca
- [ ] **Front**: cancelar → cierra sin cambios
- [ ] **Validación manual**: CA-1 — editar nombre y correo → cambios reflejados
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Admin puede modificar usuarios. Validaciones de email único. Tests pasan. Sin vulnerabilidades High.

---

## US-31 — Eliminar usuario (admin)

**Sprint:** 02

### Criterios de aceptación

1. DADO un admin en "Gestión de Cuentas", CUANDO pulsa eliminar, ENTONCES puede eliminar la cuenta y mantener al margen las inactivas.

### Tareas técnicas — Backend

- Endpoint `DELETE /api/v1/admin/users/{id}` — soft delete (campo `is_active = false`) o hard delete.
- Proteger con `require_role("admin")`.
- No permitir que un admin se elimine a sí mismo.
- Tests: eliminar usuario, auto-eliminación rechazada (400), sin permiso (403).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- `DeleteUserDialog.tsx` ya existe en `src/features/admin/accounts/components/`.
- Botón eliminar por fila → modal de confirmación "¿Estás seguro de eliminar a [nombre]?".
- "Eliminar" → `DELETE /api/v1/admin/users/{id}`, cerrar modal, refrescar lista.
- "Cancelar" → cerrar sin cambios.
- Diferenciar visualmente cuentas inactivas en la tabla (si es soft delete).

### Checklist

- [ ] **Back**: endpoint `DELETE /api/v1/admin/users/{id}` (soft o hard delete)
- [ ] **Back**: protección `require_role("admin")`
- [ ] **Back**: prevenir auto-eliminación
- [ ] **Back**: tests (eliminar, auto-eliminación, 403)
- [ ] **Front**: modal de confirmación de eliminación
- [ ] **Front**: eliminar → refresca lista
- [ ] **Front**: cuentas inactivas diferenciadas (si soft delete)
- [ ] **Validación manual**: CA-1 — eliminar usuario → desaparece o se marca inactivo
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Admin puede eliminar usuarios con confirmación. Cuentas inactivas manejadas. Tests pasan. Sin vulnerabilidades High.

---

## US-32 — Crear Cursos (Admin)

**Sprint:** 02

### Criterios de aceptación

1. DADO un admin en "Gestión de Cursos", CUANDO pulsa "+ Nuevo Curso" y completa el formulario, ENTONCES el sistema agrega el curso y permite publicarlo para los estudiantes.

### Tareas técnicas — Backend

- Modelo `Course` persistido en DB: id, code, name, credits, cycle, is_published, created_at.
- Modelo `Section` en DB: id, course_id (FK), section_name, professor_id (FK), schedules (JSONB o tabla separada).
- Migraciones Alembic.
- Endpoint `POST /api/v1/admin/courses` — crear curso con secciones.
- Endpoint `PATCH /api/v1/admin/courses/{id}/publish` — publicar curso (is_published = true).
- Endpoint `GET /api/v1/courses` — listar cursos publicados (para estudiantes).
- Proteger endpoints admin con `require_role("admin")`.
- Tests: crear curso, publicar, listar publicados, sin permiso (403).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Página `/admin/courses` ya existe con `AddCourseDialog.tsx`, `CoursesTable.tsx`.
- Botón "+ Nuevo Curso" → modal con formulario: código, nombre, créditos, ciclo, secciones (profesor + horarios por sección).
- "Agregar" → `POST /api/v1/admin/courses`, cerrar modal, refrescar tabla.
- Botón "Publicar" por curso → `PATCH /api/v1/admin/courses/{id}/publish`.
- "Cancelar" → cerrar modal sin cambios.

### Checklist

- [ ] **Back**: modelo Course + Section + migraciones Alembic
- [ ] **Back**: endpoint `POST /api/v1/admin/courses`
- [ ] **Back**: endpoint `PATCH /api/v1/admin/courses/{id}/publish`
- [ ] **Back**: endpoint `GET /api/v1/courses` (públicos)
- [ ] **Back**: protección `require_role("admin")`
- [ ] **Back**: tests (crear, publicar, listar, 403)
- [ ] **Front**: modal de creación con formulario completo
- [ ] **Front**: secciones dinámicas (agregar/quitar secciones en el formulario)
- [ ] **Front**: botón "Publicar" por curso
- [ ] **Front**: cancelar → cierra sin cambios
- [ ] **Validación manual**: CA-1 — crear curso con secciones → aparece en tabla admin
- [ ] **Validación manual**: publicar → visible para estudiantes
- [ ] **Code review** completado
- [ ] **Merge a QA**

### Definition of Done

- Admin puede crear y publicar cursos con secciones. Estudiantes ven solo cursos publicados. Tests pasan con cobertura >= 80%. Sin vulnerabilidades High.

---

## US-10 — Descargar Horario

**Sprint:** 02 · **Nueva (backlog oficial 2026-05-31)**

### Criterios de aceptación

1. DADO un estudiante visualizando un horario, CUANDO presiona "Descargar", ENTONCES el sistema genera el archivo en el formato disponible y permite descargarlo.
2. DADO el flujo de descarga, CUANDO el estudiante lo cancela, ENTONCES no se descarga nada y la vista queda intacta.

### Tareas técnicas — Backend

- **Decisión pendiente:** la descarga puede ser **100% cliente** (render del horario a PDF/imagen en el FE) y NO requerir backend. Si se quiere PDF generado en servidor, agregar `GET /api/v1/schedules/saved/{id}/pdf` (o `POST /schedules/export`) que renderice el horario.
- Tests si se implementa server-side.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Botón "Descargar" en `ResultsStep`/`ScheduleModal`. Exportar el horario actual a PDF o imagen (cliente). Manejar cancelación sin efectos.

### Estado actual

No implementado (hoy el botón "Guardar" está deshabilitado y no hay descarga). Relacionada con US-09 (guardar) pero independiente.

### Definition of Done

- El estudiante descarga su horario en un formato usable; cancelar no descarga. Tests pasan (si hay backend). Sin vulnerabilidades High.

---

## US-11 — Generar Nuevo Horario

**Sprint:** 02 · **Nueva (backlog oficial 2026-05-31)**

### Criterios de aceptación

1. DADO un estudiante con un horario generado, CUANDO inicia un nuevo proceso, ENTONCES el flujo se reinicia y limpia los datos anteriores si se confirma.
2. DADO el reinicio, CUANDO el estudiante cancela, ENTONCES se mantiene el estado actual.

### Tareas técnicas — Backend

- n/a (todo el estado del wizard vive en el FE).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- **Ya implementado:** `ScheduleModal` tiene "Crear nuevo" (→ `onReset` = `wizard.reset`, limpia estado + `localStorage['smartsched.wizard']`) y "Finalizar" (→ `clearPersisted`). Al volver al generador arranca en el paso 1.

### Estado actual

🟢 FE puro, prácticamente hecho. **Nota de producto:** Carlos decidió **NO** añadir confirmación destructiva al reiniciar (flujo rápido) — no re-proponer. El CA-1 dice "limpia si se confirma": revisar si se requiere un paso de confirmación explícito o si el botón separado ya satisface el criterio.

### Definition of Done

- Reiniciar limpia el flujo; cancelar mantiene el estado. Sin vulnerabilidades High.

---

### SPRINT 03

---

## US-13 — Guardar Conversaciones

**Sprint:** 03 · **Nueva (backlog oficial 2026-05-31)**

### Criterios de aceptación

1. DADO un estudiante conversando con el agente IA, CUANDO envía y recibe mensajes, ENTONCES el sistema guarda mensajes y respuestas y muestra las conversaciones previas asociadas a su usuario.

### Tareas técnicas — Backend

- Persistir las conversaciones en DB (hoy son **in-memory** en `app/domains/chat/store.py`): modelos `Conversation` (id, user_id FK, title, created_at) y `Message` (id, conversation_id FK, role, content, created_at) + migración Alembic.
- Ligar cada conversación al usuario autenticado (`get_current_user`); `GET /chat/conversations` filtra por `user_id`.
- Tests: persistencia, aislamiento por usuario, 401 sin token.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- `features/ai-agent` ya lista/usa conversaciones vía API. Al persistir, enviar `Authorization: Bearer` (`getToken()`) y mostrar el historial del usuario.

### Estado actual

🟢 **Backend listo (2026-06-01):** conversaciones y mensajes **persistidos en BD** (`chat/models.py` `Conversation`/`Message`, FK `user_id` CASCADE, migración `0010`), ligados al usuario autenticado y protegidos con `get_current_user`. Repositorio filtra por `user_id` y el detalle reconstruye el historial. **Falta solo (FE):** que `features/ai-agent` envíe `Authorization: Bearer` (`getToken()`) — hoy daría 401 — y aplicar la migración a Neon (`alembic upgrade head`).

### Definition of Done

- Conversaciones y mensajes persistidos por usuario; historial visible. Tests pasan. Sin vulnerabilidades High.

---

## US-14 — Eliminar Conversaciones

**Sprint:** 03 · **Nueva (backlog oficial 2026-05-31)**

### Criterios de aceptación

1. DADO un estudiante en su historial, CUANDO elimina una conversación (con confirmación), ENTONCES desaparece y el historial se actualiza.

### Tareas técnicas — Backend

- `DELETE /api/v1/chat/conversations/{id}` **ya existe** (in-memory). Al persistir (US-13), validar **ownership** (que la conversación sea del usuario) y proteger con `get_current_user`.
- Tests: eliminar propia (204), eliminar ajena (404/403).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- `features/ai-agent` ya tiene la **papelera** para eliminar conversaciones. Añadir confirmación si el CA lo exige.

### Estado actual

🟢 **Backend listo (2026-06-01):** `DELETE /chat/conversations/{id}` **persistido** y con **validación de ownership** (404 si la conversación no es del usuario). Falta: que el FE envíe `Authorization: Bearer` y, si el CA lo exige, confirmación destructiva (decisión FE). Papelera en FE ya existe.

### Definition of Done

- El estudiante elimina conversaciones con confirmación; historial actualizado; solo elimina las suyas. Tests pasan. Sin vulnerabilidades High.

---

## US-15 — Consultar Reputación de Profesor

**Sprint:** 03 · **Nueva (backlog oficial 2026-05-31)** · 🤖 **Se resuelve vía el AGENTE IA**

> 🤖 **(Aclaración de Carlos 2026-05-31.)** Esta consulta la responde el **agente IA** con conocimiento del LLM — **NO** requiere la sección de profesores ni los modelos `Professor`/`Review` en DB. Es una extensión de **US-12** (chat), no un módulo aparte. La US-21 "Agregar Reseñas" también es del agente IA y **no requiere la sección de profesores aún**. (Las tablas siguen *diseñadas* en `docs/DATA_MODEL.md` por si en el futuro se quiere data-driven.)

### Criterios de aceptación

1. DADO un estudiante en el agente IA, CUANDO pregunta por la reputación de un profesor, ENTONCES el asistente responde con el resumen disponible.
2. DADO un profesor sin información, ENTONCES el asistente informa que no hay datos.

### Tareas técnicas — Backend

- **Vía agente IA:** reforzar el prompt/instrucción del agente (`ulima_agent/`) para responder consultas de reputación de profesores. **NO** crear `Professor`/`Review` ni endpoints REST por ahora.
- (Opcional futuro) si se quiere data-driven, recién ahí crear modelos + `GET /professors[/{id}]`.

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Se usa el chat existente (`features/ai-agent`). **No** se cablea `features/professors` con datos reales todavía.

### Estado actual

🟡 Respondible por el agente IA (US-12 ya conectado). Falta reforzar el prompt. La sección de profesores sigue mock y **no** se conecta aún.

### Definition of Done

- El estudiante obtiene del agente IA un resumen de reputación; "sin datos" cuando aplica. Sin vulnerabilidades High.

---

## US-16 — Consultar Dificultad de Curso

**Sprint:** 03 · **Nueva (backlog oficial 2026-05-31)** · 🤖 **Se resuelve vía el AGENTE IA**

> 🤖 **(Carlos 2026-05-31)** La responde el **agente IA** (conocimiento del LLM). **NO** requiere DB de cursos ni sección dedicada por ahora; es extensión de US-12.

### Criterios de aceptación

1. DADO un estudiante en el agente IA, CUANDO pregunta por la dificultad de un curso, ENTONCES el asistente responde con el nivel/descripción, o informa si no tiene datos.

### Tareas técnicas — Backend

- **Vía agente IA:** reforzar el prompt del agente para responder dificultad de cursos. Sin endpoints REST ni modelo `Course` por ahora.
- (Opcional futuro) data-driven con `GET /courses/{id}` cuando exista `Course` (US-32).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Se usa el chat existente (`features/ai-agent`).

### Estado actual

🟡 Respondible por el agente IA. Falta reforzar el prompt.

### Definition of Done

- El estudiante obtiene del agente IA la dificultad de un curso; maneja "sin datos". Sin vulnerabilidades High.

---

## US-17 — Consultar Prerrequisitos

**Sprint:** 03 · **Nueva (backlog oficial 2026-05-31)** · 🤖 **Se resuelve vía el AGENTE IA**

> 🤖 **(Carlos 2026-05-31)** La responde el **agente IA** (conocimiento del LLM). **NO** requiere la tabla `course_prerequisites` ni sección dedicada por ahora; es extensión de US-12.

### Criterios de aceptación

1. DADO un estudiante en el agente IA, CUANDO pregunta por los prerrequisitos de un curso, ENTONCES el asistente responde con los prerrequisitos, o informa si no tiene datos.

### Tareas técnicas — Backend

- **Vía agente IA:** reforzar el prompt del agente para responder prerrequisitos. Sin tabla `course_prerequisites` ni endpoints por ahora.
- (Opcional futuro) data-driven con `GET /courses/{id}/prerequisites` cuando exista `Course` (US-32).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Se usa el chat existente (`features/ai-agent`).

### Estado actual

🟡 Respondible por el agente IA. Falta reforzar el prompt.

### Definition of Done

- El estudiante obtiene del agente IA los prerrequisitos de un curso; maneja "sin datos". Sin vulnerabilidades High.

---

## US-18 — Consultar Cursos por Nivel

**Sprint:** 03 · **Nueva (backlog oficial 2026-05-31)** · 🤖 **Se resuelve vía el AGENTE IA**

> 🤖 **(Carlos 2026-05-31)** La responde el **agente IA** (conocimiento del LLM). **NO** requiere DB de cursos ni catálogo dedicado por ahora; es extensión de US-12.

### Criterios de aceptación

1. DADO un estudiante en el agente IA, CUANDO pregunta por cursos de un nivel/ciclo, ENTONCES el asistente responde con los cursos correspondientes, o informa si no tiene datos.

### Tareas técnicas — Backend

- **Vía agente IA:** reforzar el prompt del agente para responder cursos por nivel. Sin `GET /courses?level=` ni modelo `Course` por ahora.
- (Opcional futuro) data-driven con `GET /courses?level=` cuando exista `Course` (US-32).

### Tareas técnicas — Frontend (`../smartsched-ulima-web-frontend`)

- Se usa el chat existente (`features/ai-agent`).

### Estado actual

🟡 Respondible por el agente IA. Falta reforzar el prompt.

### Definition of Done

- El estudiante obtiene del agente IA los cursos por nivel; maneja "sin datos". Sin vulnerabilidades High.

---

## Checklist global de Release 01

- [ ] Todas las HU del Sprint 01 completadas y mergeadas a QA
- [ ] Todas las HU del Sprint 02 completadas y mergeadas a QA
- [ ] Testing completo en entorno QA (todos los criterios de aceptación validados manualmente)
- [ ] Cobertura de tests >= 80% en backend (`uv run pytest --cov=app`)
- [ ] Lint limpio en backend (`uv run ruff check .`) y frontend (`npm run lint`)
- [ ] Type check limpio en backend (`uv run mypy app/`)
- [ ] Cero vulnerabilidades High (revisión de dependencias y código)
- [ ] Migraciones Alembic aplicadas correctamente en QA
- [ ] Variables de entorno de producción configuradas en Secret Manager
- [ ] Build de producción exitoso en frontend (`npm run build`)
- [ ] Deploy a Cloud Run (backend) verificado
- [ ] Deploy a Vercel/Cloud Run (frontend) verificado
- [ ] Smoke test post-deploy en producción
- [ ] Code review final de todo el release aprobado
