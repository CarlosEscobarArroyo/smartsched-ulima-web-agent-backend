# PATTERNS.md — Patrones de diseño del backend

> **Alcance:** patrones de diseño (GoF) aplicados en el backend de SmartSched-Ulima
> (FastAPI + SQLAlchemy async). Cada patrón está **anotado en el código** con un
> comentario greppable, de modo que puedas ir del documento al código con un `grep`.
> **Clasificación:** se usa la taxonomía GoF (*creacional* / *estructural* / *de
> comportamiento*). Ojo: **Singleton es creacional, no estructural** (error común).

---

## Cómo encontrar cada patrón en el código

Cada uso lleva un comentario con el nombre del patrón entre paréntesis su categoría:

```bash
grep -rn "Singleton"            app/   # 6 usos (creacional)
grep -rn "Factory / provider"  app/   # 2 usos (creacional)
grep -rn "Adapter (estructural)" app/ # 4 usos (estructural)
grep -rn "Facade (estructural)"  app/ # 2 usos (estructural)
```

---

## Tabla resumen

| Patrón | Categoría GoF | Usos | Dónde |
|---|---|---|---|
| **Singleton** | Creacional | 6 | `db/session.py`, `core/config.py`, `integrations/bucket/bucket.py`, `integrations/ocr/client.py`, `integrations/ocr/structurer.py`, `integrations/agent/ulima_agent.py` |
| **Factory / provider** | Creacional | 2 | `integrations/ocr/structurer.py` (`get_course_structurer`), `integrations/agent/ulima_agent.py` (`get_ulima_agent`) |
| **Adapter** | **Estructural** | 4 | `domains/schedules/service.py`, `integrations/bucket/bucket.py`, `integrations/ocr/client.py`, `integrations/email/client.py` |
| **Facade** | **Estructural** | 2 | `integrations/agent/ulima_agent.py` (`UlimaAgentClient`), `integrations/ocr/structurer.py` (`CourseStructurer`) |

---

## Singleton (creacional)

**Intención:** garantizar una única instancia por proceso y un punto de acceso global a
ella. Aquí el objetivo práctico es **no recrear clientes/conexiones costosas** (BD, GCP,
LLM, configuración) en cada request.

Se implementa de **dos formas** en el backend:

### a) Instancia a nivel de módulo

El objeto se crea una vez al importar el módulo y se comparte en todo el proceso.

| Archivo | Instancia | Notas |
|---|---|---|
| `app/db/session.py` | `engine`, `AsyncSessionLocal` | El engine/sessionmaker se crean una vez; `get_db()` abre una sesión **efímera por request** desde ese pool. |
| `app/integrations/ocr/structurer.py` | `_structurer` | El cliente `genai`/Vertex interno se crea **perezosamente** (`_get_client`). |
| `app/integrations/agent/ulima_agent.py` | `_agent_client` | El `InMemoryRunner` de ADK interno se crea **perezosamente** (`_get_runner`). |

### b) `@lru_cache` sobre una función factoría

`@lru_cache` sin argumentos memoiza el primer resultado → una única instancia por proceso.

| Archivo | Función | Notas |
|---|---|---|
| `app/core/config.py` | `get_settings()` | Lee el entorno/`.env` una sola vez. |
| `app/integrations/bucket/bucket.py` | `_get_client()` | Cliente `storage.Client` de GCS. |
| `app/integrations/ocr/client.py` | `_get_client()` | Cliente `vision.ImageAnnotatorClient` (Cloud Vision). *Huérfano:* el OCR ya va por Gemini, no por Vision. |

> **En tests:** para los singletons con `@lru_cache`, llamar `_get_client.cache_clear()`
> (o `get_settings.cache_clear()`) **antes** de parchear, o el mock no tendrá efecto.

**Lazy init:** los dos wrappers de LLM (`structurer`, `agent`) difieren la creación del
cliente pesado para que **importar el módulo no exija credenciales GCP** — así los tests
que no usan el cliente pueden mockearlo sin autenticarse.

---

## Factory / provider (creacional)

**Intención:** centralizar la obtención de un objeto detrás de una función, en vez de que
el llamador lo construya. En este proyecto las funciones `get_*` son **proveedores para
inyección de dependencias** (FastAPI `Depends`): devuelven el singleton y permiten
**sobrescribirlo en tests** (`app.dependency_overrides`).

| Archivo | Función | Devuelve |
|---|---|---|
| `app/integrations/ocr/structurer.py` | `get_course_structurer()` | El singleton `_structurer`. |
| `app/integrations/agent/ulima_agent.py` | `get_ulima_agent()` | El singleton `_agent_client`. |

> ⚠️ **Precisión de nomenclatura:** son *factorías-provider* (función factoría simple +
> inyección de dependencias), **no** el *Factory Method* clásico de GoF (que usa herencia
> para que subclases decidan qué clase instanciar). Se documenta como "Factory / provider"
> para no sobre-afirmar. `get_settings()` cumple un rol equivalente pero está anotada como
> **Singleton** (la función `@lru_cache` *es* la implementación del singleton).

---

## Adapter (estructural)

**Intención:** convertir la interfaz de un componente en la interfaz que el resto del
sistema espera. Es el patrón estructural **dominante** del backend: toda la capa
`app/integrations/` son adaptadores a sistemas externos.

| Archivo | Adapta… | Interfaz expuesta |
|---|---|---|
| `app/domains/schedules/service.py` | El **contrato del frontend** (strings `horarios`/`blockedSlots`) ⇄ los objetos del generador puro (`ClassSection`/`TimeBlock`). | `generate(payload)` + helpers `_parse_*` (conversión en ambos sentidos). |
| `app/integrations/bucket/bucket.py` | El SDK de **Google Cloud Storage**. | `upload_file(filename, data, content_type)` |
| `app/integrations/ocr/client.py` | El SDK de **Cloud Vision**. | `detect_document_text(image_bytes)` |
| `app/integrations/email/client.py` | La API de **`smtplib`** (stdlib). | `send_reset_email(...)`, `send_support_email(...)` |

El caso más "de libro" es `schedules/service.py`: recibe el shape del FE, lo traduce al
dominio, invoca `generate_schedules()` y **reconstruye** el shape `{options:[{courses:…}]}`
que el FE espera.

---

## Facade (estructural)

**Intención:** ofrecer una interfaz simple y unificada sobre un **subsistema complejo**,
escondiendo sus múltiples piezas. Se aplica en los dos wrappers de LLM.

| Archivo | Subsistema que esconde | Interfaz simple |
|---|---|---|
| `app/integrations/agent/ulima_agent.py` (`UlimaAgentClient`) | ADK: `InMemoryRunner`, `session_service`, `Event`, `types.Content`, el bucle `run_async`, la rehidratación de historial. | `create_session()` · `ensure_session()` · `ask()` |
| `app/integrations/ocr/structurer.py` (`CourseStructurer`) | SDK `google.genai`/Vertex: `genai.Client`, `types.Part`, `GenerateContentConfig`, `response_schema`, parseo de la respuesta. | `structure(images)` |

Cada clase es a la vez el **Facade** (interfaz simple) y, en su instancia de módulo, el
**Singleton** (una por proceso).

---

## Adapter vs. Facade — criterio aplicado

Los wrappers de `integrations/` cumplen rasgos de ambos (traducen interfaz **y**
simplifican). El criterio usado para etiquetar cada archivo:

- **Adapter** → wrappers *finos* de un SDK cuyo objetivo principal es **traducir la
  interfaz** (`bucket`, `ocr/client`, `email`) y la traducción de contrato FE⇄dominio
  (`schedules/service`).
- **Facade** → wrappers que **esconden un subsistema grande** con muchas piezas
  interdependientes (`agent`, `structurer`).

Ambas lecturas son defendibles; lo importante es la coherencia de la anotación.

---

## Qué NO se clasifica aquí (para no sobre-afirmar)

- **Repository** (`domains/chat/repository.py`, `admin/`, `professors/`, `users/`) — patrón
  muy usado en el backend, pero es **arquitectónico/DDD**, no un patrón GoF estructural.
- **"Proxy"** — el `CLAUDE.md` llama a `domains/chat/` *"proxy al agente IA"* de forma
  coloquial; **no** es el Proxy GoF estricto (mismo interfaz + control de acceso), sino un
  service/facade. No etiquetar como Proxy en un informe formal.
- **Inyección de dependencias** (FastAPI `Depends`) — mecanismo arquitectónico, no un
  patrón GoF (aunque habilita las factorías-provider de arriba).

---

## Apéndice — comandos de verificación

```bash
# Ubicar todos los patrones anotados
grep -rn "Singleton\|Factory / provider\|Adapter (estructural)\|Facade (estructural)" app/

# Lint de los archivos anotados (deben pasar limpio)
uv run ruff check app/db/session.py app/core/config.py \
  app/integrations/bucket/bucket.py app/integrations/ocr/client.py \
  app/integrations/ocr/structurer.py app/integrations/agent/ulima_agent.py \
  app/integrations/email/client.py app/domains/schedules/service.py
```
