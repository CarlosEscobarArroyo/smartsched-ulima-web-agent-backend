# Pruebas de calidad (QA) — Backend

Carpeta con las pruebas que demuestran las tres técnicas exigidas, aplicadas al
**backend** (FastAPI + pytest). Es el equivalente en Python de lo que en Java se
hace con **JUnit** (pruebas) y **Mockito** (dobles de prueba/mocks).

> El frontend tiene su propia carpeta espejo en
> `../../smartsched-ulima-web-frontend/src/__tests__/qa/` (con Vitest).

## Las tres técnicas

La rúbrica exige tres técnicas: **caja blanca** (complejidad ciclomática > 4), **caja
negra** (funcionalidad con > 4 campos de entrada) y **prueba unitaria** (≥ 4 casos). Este
backend contiene tres juegos completos, cada uno sobre módulos distintos.

## Cómo ejecutar

```bash
uv run pytest tests/qa/ -v          # solo estas pruebas, en detalle
uv run pytest tests/qa/             # modo silencioso
uv run pytest                       # toda la suite del backend
```

## Los tests del backend y por qué cumplen cada criterio

| Archivo | Técnica | Objetivo probado | Cumple porque… |
|---|---|---|---|
| `test_caja_blanca_generador.py` | **Caja blanca** | `generate_schedules()` (backtracking en `app/integrations/generator/generator.py`) | Complejidad ciclomática **V(G) = 10 > 4**. Cada test recorre un camino/rama distinta (D1..D9). |
| `test_caja_negra_crear_curso.py` | **Caja negra** | `POST /api/v1/admin/courses` | La funcionalidad tiene **5 campos > 4** (code, name, level, prerequisites, professor_id). Solo entradas→salidas con **particiones de equivalencia** y **valores límite**. |
| `test_unitaria_solapamiento.py` | **Prueba unitaria** | `TimeBlock.overlaps()` | Método puro y aislado con **6 casos** (≥ 4), incluyendo el valor límite de bordes que se tocan. |
| `test_caja_blanca_authenticate.py` | **Caja blanca** | `authenticate()` login + bloqueo (`app/domains/auth/service.py`) | **V(G) = 6 > 4**. Cada test cubre una rama: éxito, 401, incremento, bloqueo (423) y cuenta ya bloqueada. |
| `test_caja_negra_crear_profesor.py` | **Caja negra** | `POST /api/v1/admin/professors` | **5 campos > 4** (name, department, degree, bio, email). Particiones y valores límite (largo 1, 2, 120, 121…) + 401/403. |
| `test_unitaria_is_locked.py` | **Prueba unitaria** | `_is_locked()` | Método puro con **5 casos** (≥ 4): sin bloqueo, vigente, expirado y las dos ramas de zona horaria (naive/aware). |
| `test_caja_blanca_merge_courses.py` | **Caja blanca** | `_merge_courses()` deduplicación del OCR (`app/integrations/ocr/service.py`) | **V(G) = 7 > 4**. Cada test cubre una rama: curso nuevo, repetido (junta secciones), sección duplicada y la clave por código/nombre. |
| `test_caja_negra_ocr_curso.py` | **Caja negra** | `OCRCurso` (contrato de salida del OCR, `app/integrations/ocr/schemas.py`) | **5 campos > 4** (codigo, nombre, creditos, nivel, secciones). Particiones de tipo válido/ inválido y campo obligatorio/ opcional. |
| `test_unitaria_parse_horario.py` | **Prueba unitaria** | `_parse_horario()` (`app/domains/schedules/service.py`) | Función pura con **6 casos** (≥ 4): parseo correcto, día inválido, formato irreconocible, hora fuera de rango (límite) y rango invertido. |

### Notas por técnica

- **Caja blanca (estructural):** los casos se diseñan MIRANDO el código para recorrer
  cada camino independiente. Cada archivo documenta el cálculo de la **complejidad
  ciclomática de McCabe** (`V(G) = 1 + puntos de decisión`) y, en cada docstring,
  qué punto de decisión (D1, D2, …) cubre el test.
- **Caja negra (contrato):** se prueba solo el par entrada→salida, sin mirar el
  interno, con **particiones de equivalencia** y **valores límite**. Para los
  endpoints se incluyen además las reglas observables (401 sin token, 403 por rol).
- **Prueba unitaria:** valida un método puro y aislado (sin BD ni HTTP). `_is_locked`
  usa un `User` transitorio en memoria; `overlaps`/`_parse_horario` no tocan nada externo.

## Relación con JUnit/Mockito

- `pytest` ≈ **JUnit**: `def test_*` con `assert` ≈ `@Test` con `assertEquals`.
- En el frontend, la prueba de caja blanca reemplaza la red (`fetch`) por un mock
  (`vi.fn()`), que es el equivalente directo de **Mockito** (`mock()` + `verify()`).
  En el backend, las cajas negras de endpoints usan el `AsyncClient` de FastAPI sobre
  una BD SQLite en memoria (`tests/conftest.py`), evitando dependencias externas reales.
