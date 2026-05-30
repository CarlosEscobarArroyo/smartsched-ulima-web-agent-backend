# CONTRACTS.md — Contrato de API Frontend ↔ Backend

> **Fuente:** extraído del código real del frontend (`smartsched-ulima-web-frontend`) el **2026-05-28**.
> Las *server actions* mock del FE **son la especificación**: definen el shape que cada pantalla
> envía y espera de vuelta. Este documento traduce eso a endpoints que el backend debe implementar.
>
> A hoy **nada está conectado** (ver `CLAUDE.md` → "Estado de integración Frontend ↔ Backend").
> Este archivo es el blueprint para construir el backend y luego reemplazar los mocks del FE.

---

## Convenciones globales

- **Base URL:** `{NEXT_PUBLIC_API_URL}/api/v1` (FE default `http://localhost:8000`).
- **El wrapper `{ status, message, ... }` es del FE, no del backend.** Las server actions del FE
  envuelven la respuesta en `ActionState` (`status: 'idle'|'success'|'error'`). El **backend debe
  devolver la entidad "pelada" + códigos HTTP REST** (201 al crear, 200 al leer/editar, 204 al
  borrar; 4xx con `{ "detail": "..." }` en error). El FE adapta ese resultado a su `ActionState`.
  → En las tablas, "Response (FE espera)" muestra lo que la pantalla consume; "Backend devuelve"
  muestra lo recomendado en REST.
- **Validación:** las reglas vienen de los `*.schema.ts` (Zod). **Replicarlas en Pydantic** para que
  FE y BE rechacen lo mismo.
- **Fechas:** siempre **ISO 8601 string** (`createdAt`, `date`, `timestamp`, `expiresAt`).
- **Autenticación:** estrategia de token **PENDIENTE** (cookie HttpOnly vs `Bearer`). Marcadas:
  - 🔒 requiere usuario autenticado · 🔒admin requiere rol `admin`.
- **Rol:** el FE usa `"student" | "admin"` (no `"estudiante"`). El backend debe emitir/aceptar
  estos valores. Ver mismatches.

---

## 1. Auth  (US-24, US-25)

| Op | Método | Ruta | Auth |
|---|---|---|---|
| login | POST | `/api/v1/auth/login` | público |
| reset password | POST | `/api/v1/auth/reset-password` | público |
| google login | POST | `/api/v1/auth/google` | público (FE aún no lo implementa) |

### login — `POST /api/v1/auth/login`
- **Request** (JSON recomendado; el FE hoy arma FormData `email`,`password`):
  - `email`: string, requerido, formato email
  - `password`: string, requerido, **min 8 chars**
- **Response (FE espera):** `{ error: string | null, session: { user: { id, email, name, role }, expiresAt } | null }`
- **Backend devuelve (recomendado):** `200 { access_token, token_type: "bearer", user: { id, email, name, role } }` (+ `refresh_token` opcional, o cookie HttpOnly según decisión). El FE construye su `Session` a partir de esto.
- **Reglas:** 3 intentos → bloqueo 15 min (`423`); credenciales inválidas → `401`. `role ∈ {student, admin}`.
- **Mock actual:** `alumno@ulima.edu.pe / Alumno123` (student), `admin@ulima.edu.pe / Admin1234` (admin).

### reset password — `POST /api/v1/auth/reset-password`
- **Request:** `email` (email), `newPassword` (min 8), `confirmPassword` (debe igualar a `newPassword`).
- **Response (FE espera):** `{ status, message }`. Backend: `200 { ok: true }` / `400` con detalle.
- ⚠️ **Mismatch de flujo:** el FE hace reset **directo** (email + nueva contraseña, sin token). La US-25 pide flujo seguro: `forgot-password` → email con enlace/token → `reset-password?token=...`. Decidir (ver mismatches).

### google login — `POST /api/v1/auth/google` *(backlog; FE pendiente)*
- Request: `{ id_token }` (Google). Response igual a login.

**Tipos FE (`features/auth/types.ts`):**
```ts
type Role = "student" | "admin";
type User = { id: string; email: string; name: string; role: Role };
type Session = { user: User; expiresAt: string };
```

---

## 2. Generador de horarios  (US-01, US-02, US-06, US-07, US-09)

| Op | Método | Ruta | Auth |
|---|---|---|---|
| OCR de imagen/PDF | POST | `/api/v1/ocr/process-image` | público (de momento) |
| generar combinaciones | POST | `/api/v1/schedules/generate` | público (de momento) |
| guardar horario | POST | `/api/v1/schedules/saved` | 🔒 |
| listar guardados | GET | `/api/v1/schedules/saved` | 🔒 |
| eliminar guardado | DELETE | `/api/v1/schedules/saved/{id}` | 🔒 |

### OCR — `POST /api/v1/ocr/process-image`
- **Request:** `multipart/form-data`, clave **`files`** = `File[]`. Cliente valida: ≥1 archivo; tipos `application/pdf, image/png, image/jpeg, image/webp`; **≤10 MB** c/u.
  - ⚠️ **Decisión backend (2026-05-29): solo imágenes.** El backend acepta únicamente `image/png`, `image/jpeg`, `image/webp` (≤10 MB) y **rechaza PDF** (422). Procesamiento **inline** con Cloud Vision (`vision.Image(content=bytes)`, OCR síncrono) — **sin subir a GCS**. El cliente FE aún declara `application/pdf`; si se quisieran PDFs habría que reintroducir GCS + el modo *async batch* de Vision. `/api/v1/upload` (bucket) NO participa de este flujo.
- **Response (FE espera):**
```json
{ "cursos": [ {
  "codigo": "string", "nombre": "string", "creditos": 0, "nivel": 0,
  "secciones": [ {
    "seccion": "string", "profesor": "string", "vacantes": 0,
    "horario": [ { "dia": "MIE", "inicio": "HH:MM", "fin": "HH:MM", "aula": "string|null" } ]
  } ]
} ] }
```
- **Nota:** este shape **ya coincide** con `parse_ocr_to_sections()` del backend (lee `nombre`, `secciones[].seccion`, `horario[].{dia,inicio,fin}` con `DAY_MAP` LUN/MAR/MIE/JUE/VIE/SAB/DOM). Los campos extra (`codigo,creditos,nivel,vacantes,aula`) son ignorados por el parser pero los usa el FE.
- ⚠️ **Mismatch de nombre:** el backlog US-01 nombra el endpoint `/ocr/extract`. El **FE ya llama a `/ocr/process-image`** → implementar ese nombre (o ambos como alias).
- **Fallback FE:** si el endpoint falla, el FE usa `ocr_clean_output_example.json` local. Funciona en demo aun sin backend.

### generar — `POST /api/v1/schedules/generate`  *(decisión: la generación vive en el backend)*
- **Request (JSON):** `{ courses: DetectedCourse[], blockedSlots: string[] }`
  - `DetectedCourse`: `{ id, code, name, schedule, sections: DetectedSection[], selected: boolean }`
  - `DetectedSection`: `{ id, seccion, profesor, vacantes?, aula?, horarios: string[] }`
  - `horarios[i]` es **string**: `"Lun 12:00-13:00 Aula 850014"` (regex `^([A-Za-z]+)\s+(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})`).
  - `blockedSlots`: strings `"Dia-Hora"`, ej. `["Lun-6","Mar-11","Vie-14"]` (hora entera 6..22; `Lun-6` = 06:00–07:00). Días: `Lun,Mar,Mie,Jue,Vie,Sab,Dom`.
  - Validación: ≥1 curso con `selected=true`; cada curso activo con `sections.length>0`.
- **Response (FE espera):**
```ts
{ status, message, schedule: { id: string, options: Array<{ id: string, courses: Array<DetectedCourse & { selectedSection: DetectedSection }> }> } | null }
```
  - `MAX_OPTIONS = 20`. Si 0 combinaciones → error / `schedule=null`. Timeout objetivo 2 min (US-07).
- **⚙️ Nota de implementación:** existe un **gap de formato** con el generador del backend
  (`integrations/generator/generator.py` usa `ClassSection`/`TimeBlock` con `day:int 0-6` y `time`).
  El nuevo `schedules/service.py` debe **adaptar**: parsear los strings `horarios`/`blockedSlots` del FE
  → `TimeBlock`, correr `generate_schedules()`, y reconstruir el shape `GeneratedSchedule` del FE
  (manteniendo `selectedSection` por curso). Mantener el contrato del FE intacto para no tocar la UI.

### guardar / listar / eliminar horario  (US-09) — 🔒
- ⚠️ El FE **muestra** `savedSchedules` (en el perfil) pero **no tiene aún** la acción de guardar
  (el botón "Guardar" en `ResultsStep` no tiene handler). Estos endpoints son **nuevos** y el FE
  deberá cablearse a ellos.
- `POST /schedules/saved` → body `{ name: string, schedule_data: <opción elegida> }`, límite **10** por usuario (`409` si excede). Devuelve `SavedSchedule`.
- `GET /schedules/saved` → `SavedSchedule[]`.
- `DELETE /schedules/saved/{id}` → `204`.
- **`SavedSchedule` (shape FE, `features/profile/types.ts`):** `{ id, name, savedAt: string (ISO) }`. El perfil lo consume bajo la clave `schedules` (ver §5). Definir qué payload completo del horario se persiste internamente (`schedule_data`).

---

## 3. Agente IA  (US-12)

| Op | Método | Ruta | Auth |
|---|---|---|---|
| enviar mensaje | POST | `/api/v1/chat` | 🔒 |
| listar conversaciones | GET | `/api/v1/chat/conversations` | 🔒 |
| crear conversación | POST | `/api/v1/chat/conversations` | 🔒 |

### enviar mensaje — `POST /api/v1/chat`  *(hoy stub; requiere rework)*
- **Request (FE espera enviar):** `{ mode: ChatMode, text: string }` (`text` non-empty).
- ⚠️ **Mismatch con el backend actual:** el stub espera `{ message, session_id }` y devuelve `{ reply, session_id }`. El FE envía `{ mode, text }` y espera un **`Message` estructurado** (unión discriminada por `kind`). Hay que **rehacer `ChatRequest`/`ChatResponse`** para matchear el FE.
- **Response (FE espera):** un `Message` cuyo `kind` depende del `mode`:
```ts
type ChatMode = "professorReputation" | "courseDifficulty" | "coursePrerequisites";
// kind:"text"          → { id, role:"assistant", timestamp, kind, text }
// kind:"difficulty"    → { ...text, course, level, percentage }   (courseDifficulty)
// kind:"prerequisites" → { ...text, course, prerequisites: string[] } (coursePrerequisites)
```
- `role` siempre `"assistant"`. `id=uuid`, `timestamp=ISO`. El mensaje del usuario lo crea el FE.

### conversaciones — 🔒
- `GET /chat/conversations` → `Conversation[]` = `{ id, title, lastMessage, timestamp, mode }[]` (del usuario; paginación recomendada).
- `POST /chat/conversations` → crea y devuelve una `Conversation`.

---

## 4. Profesores y reseñas  (US-21)

| Op | Método | Ruta | Auth |
|---|---|---|---|
| listar profesores (+reseñas) | GET | `/api/v1/professors` | público |
| publicar reseña | POST | `/api/v1/professors/{id}/reviews` | 🔒 |

### listar — `GET /api/v1/professors`
- **Response (FE espera):** `Professor[]`
```ts
type Difficulty = "Fácil" | "Medio" | "Difícil";
type Course = { id: string; code: string; name: string };
type Review = { id: string; student: string; rating: number; comment: string; date: string };
type Professor = { id: string; name: string; course: string; initials: string; rating: number; reviews: Review[]; courses: Course[] };
```
  - ⚠️ `courses` es `Course[]` (objetos `{id,code,name}`), **no** `string[]`. `course` (singular) es un string de display.
  - El FE recibe `reviews` **anidadas** (no hay endpoint separado de reviews por ahora). `initials` y `rating` (promedio) los puede calcular el backend.

### reseña — `POST /api/v1/professors/{id}/reviews`  🔒
- **Request:** FormData FE → backend body `{ professorId: string (min 1), rating: int 1..5, comment?: string (≤500) }`. El `student` (nombre mostrado en la reseña) se toma del **usuario autenticado**.
- **Reglas:** una reseña por usuario por profesor (`409` si duplicada, US-21). `201` con la `Review` creada.

---

## 5. Perfil  (US-09 listado, datos del usuario)

| Op | Método | Ruta | Auth |
|---|---|---|---|
| leer perfil | GET | `/api/v1/profile` | 🔒 |
| actualizar perfil | PATCH | `/api/v1/profile` | 🔒 |

### leer — `GET /api/v1/profile`
- **Response (FE espera):** `ProfileSnapshot` (claves exactas: `user`, `reviews`, `schedules`)
```ts
type UserProfile = { id: string; name: string; email: string };
type ReviewSummary = { id: string; professor: string; course: string; rating: number; comment: string };
type SavedSchedule = { id: string; name: string; savedAt: string };
type ProfileSnapshot = { user: UserProfile; reviews: ReviewSummary[]; schedules: SavedSchedule[] };
```

### actualizar — `PATCH /api/v1/profile`
- **Request:** `name` (**min 2, max 80**), `email` (email).
- **Response (FE espera):** `{ status, message, user: { id, name, email } | null }`. Backend recomendado: `200 { id, name, email }` / `422` con el primer error de validación.

---

## 6. Ajustes  (US-25 reset arriba)

| Op | Método | Ruta | Auth |
|---|---|---|---|
| eliminar mi cuenta | DELETE | `/api/v1/account` | 🔒 |
| contactar soporte | POST | `/api/v1/support/contact` | público |

- **deleteAccount:** sin body (el id viene del token). `204`.
- **sendContactMessage:** `email` (email), `message` (10..1000). `202`/`200`.

---

## 7. Admin — Cuentas  (US-29, US-30, US-31) — 🔒admin

| Op | Método | Ruta |
|---|---|---|
| listar | GET | `/api/v1/admin/users` |
| crear | POST | `/api/v1/admin/users` |
| editar | PUT | `/api/v1/admin/users/{id}` |
| eliminar | DELETE | `/api/v1/admin/users/{id}` |

```ts
type AccountType = "Estudiante" | "Admin";   // ⚠️ capitalizado y en español (≠ Role de auth)
type User = { id: string; name: string; email: string; accountType: AccountType; initials: string };
```
- **listar →** `User[]`.
- **crear →** Request `name` (min 2, max 80), `code` (regex `^[a-z0-9.]+$/i` — letras, números y puntos), `accountType` (`Estudiante|Admin`). El **email se deriva**: `` `${code}@aloe.ulima.edu.pe` ``. `initials` calculadas del `name`. Devuelve `User` (`201`). ⚠️ El form **no pide password** → definir estrategia (default / invitación).
- **editar →** `id`, `name` (min 2, max 80), `email` (email, único excluyendo el propio), `accountType`. Devuelve `User`.
- **eliminar →** `204`. **Prevenir auto-eliminación** (US-31).

---

## 8. Admin — Cursos  (US-32) — 🔒admin

| Op | Método | Ruta |
|---|---|---|
| listar | GET | `/api/v1/admin/courses` |
| crear | POST | `/api/v1/admin/courses` |
| editar | PUT | `/api/v1/admin/courses/{id}` |
| eliminar | DELETE | `/api/v1/admin/courses/{id}` |

```ts
type Course = { id: string; code: string; name: string; level: string; prerequisites: string[] };
```
- **crear →** `code` (regex `^[A-Z]{2,4}\d{2,4}$`, ej `CS101`; el FE lo pasa a mayúsculas), `name` (1..120), `level` (regex `^\d{1,2}$`, ej `"1"`), `prerequisites` (string **CSV**, ej `"CS101, MAT101"` → el FE lo parsea a array). `code` único.
- **editar →** igual + `id`.
- ⚠️ **Gap con US-32:** el `Course` del FE **no tiene secciones** (profesor + horarios) **ni campo `publish`/`is_published`**, que la US-32 sí pide. Decidir si se extiende el modelo del FE o se limita el alcance.

---

## 9. Admin — Profesores  (sin US numerada; existe en el FE) — 🔒admin

| Op | Método | Ruta |
|---|---|---|
| listar | GET | `/api/v1/admin/professors` |
| crear | POST | `/api/v1/admin/professors` |
| editar | PUT | `/api/v1/admin/professors/{id}` |
| eliminar | DELETE | `/api/v1/admin/professors/{id}` |

```ts
type AdminProfessor = { id, name, initials: string, reviewCount: number };
```
- **crear →** `name` (1..100). `initials` calculadas server-side (quitando prefijos `Dr./Dra./Prof./Mg./Ing./Lic.`), `reviewCount=0`.
- **editar →** `id`, `name`. ⚠️ **Preservar `reviewCount`** (el mock del FE lo resetea a 0 por bug; el backend NO debe).
- **Nota:** `AdminProfessor` (admin) y `Professor` (vista estudiante, §4) son la **misma entidad** con dos proyecciones. Un solo modelo en el backend, dos response shapes.

---

## Mismatches y decisiones pendientes

| # | Tema | Estado FE | Qué pide el backlog / recomendación |
|---|---|---|---|
| 1 | Nombre endpoint OCR | `/ocr/process-image` | backlog dice `/ocr/extract` → **implementar el del FE** (o alias) |
| 2 | Enum de rol | auth: `"student"\|"admin"` · admin-cuentas: `"Estudiante"\|"Admin"` · backlog: `"estudiante"` | **3 encodings distintos** → unificar uno (sugerido `student/admin`) y mapear en la capa admin |
| 3 | Contrato de chat | `{mode,text}` → `Message` (unión) | stub usa `{message,session_id}`→`{reply}` → **rehacer `ChatRequest/Response`** |
| 4 | Flujo reset password | reset directo (email+newPassword) | US-25 quiere `forgot`→token→`reset` → **decidir** (seguro vs simple-MVP) |
| 5 | Modelo `Course` | sin secciones ni `publish` | US-32 quiere secciones (profe+horarios) + publicar → **extender o reducir alcance** |
| 6 | Password en alta de usuario | el form no pide password | definir default / invitación por email |
| 7 | Wrapper de respuesta | FE usa `{status,message,...}` | backend devuelve **entidad + HTTP REST**; el FE adapta |
| 8 | Estrategia de token | localStorage `smartsched.session` | cookie HttpOnly vs `Bearer` → **PENDIENTE** ("después veremos") |
| 9 | `reviewCount` en update profe | mock lo resetea a 0 | backend debe **preservarlo** |
| 10 | `initials` | calculadas en FE/mock | estandarizar: calcular y devolver desde el backend |
| 11 | Guardado de horarios (US-09) | el FE no tiene acción de guardar | crear endpoints + cablear el botón "Guardar" del FE |

---

## Apéndice — endpoints backend que YA existen (a reconciliar)

| Método | Ruta | Estado |
|---|---|---|
| GET | `/api/v1/health` | real |
| POST | `/api/v1/chat` | **stub** + contrato distinto (ver mismatch #3) |
| POST | `/api/v1/upload/` · `/upload/multiple/` | real (GCS) — el OCR podría reutilizar la subida a bucket internamente |
