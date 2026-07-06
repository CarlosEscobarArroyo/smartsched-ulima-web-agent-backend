# Pruebas de calidad (QA) — Backend

Carpeta con las pruebas que demuestran las tres técnicas exigidas, aplicadas al
**backend** (FastAPI + pytest). Es el equivalente en Python de lo que en Java se
hace con **JUnit** (pruebas) y **Mockito** (dobles de prueba/mocks).

> El frontend tiene su propia carpeta espejo en
> `../../smartsched-ulima-web-frontend/src/__tests__/qa/` (con Vitest).

## Cómo ejecutar

```bash
uv run pytest tests/qa/ -v          # solo estas pruebas, en detalle
uv run pytest tests/qa/             # modo silencioso
uv run pytest                       # toda la suite del backend
```

## Los 3 tests y por qué cumplen cada criterio

| Archivo | Técnica | Objetivo probado | Cumple el criterio porque… |
|---|---|---|---|
| `test_caja_blanca_generador.py` | **Caja blanca** | `generate_schedules()` (algoritmo de backtracking en `app/integrations/generator/generator.py`) | Complejidad ciclomática **V(G) = 10 > 4**. Cada test recorre un camino/rama distinta (ver tabla en el archivo). |
| `test_caja_negra_crear_curso.py` | **Caja negra** | `POST /api/v1/admin/courses` (crear curso) | La funcionalidad tiene **5 campos de entrada > 4** (code, name, level, prerequisites, professor_id). Se prueban solo entradas→salidas con **particiones de equivalencia** y **valores límite**. |
| `test_unitaria_solapamiento.py` | **Prueba unitaria** | `TimeBlock.overlaps()` | Valida un método puro y aislado con **6 casos** (≥ 4), incluyendo el valor límite de bordes que se tocan. |

### 1. Caja blanca — `generate_schedules()`

La caja blanca (prueba **estructural**) se diseña mirando el código para recorrer
todos sus caminos. En el archivo se documenta el cálculo de la **complejidad
ciclomática de McCabe**: `V(G) = 1 + (puntos de decisión)`. La función tiene 9
puntos de decisión (validación de `target`, filtro de bloqueos, bucles de
agrupación, poda por materias insuficientes, poda por solapamiento, etc.) →
**V(G) = 10**. Cada test indica en su docstring qué punto de decisión (D1..D9)
cubre.

### 2. Caja negra — crear curso (5 campos)

La caja negra prueba la funcionalidad **sin mirar el código interno**: solo el
contrato (entradas → salidas). Se usan:

- **Particiones de equivalencia**: entradas que se comportan igual (p. ej. "código
  vacío" siempre es 422; "curso válido" siempre es 201).
- **Valores límite**: los bordes de cada partición (largo 1, 20, 21 caracteres…).

Se cubren además las reglas de negocio observables desde afuera: 401 sin token,
403 con rol estudiante, 409 por código duplicado (normalizado a mayúsculas).

### 3. Prueba unitaria — `TimeBlock.overlaps()` (6 casos)

Método puro que decide si dos bloques de horario se cruzan. Los 6 casos:
solapamiento parcial, bordes que se tocan (valor límite → no solapan),
contención, disjuntos, distinto día e idénticos.

## Relación con JUnit/Mockito

- `pytest` ≈ **JUnit**: `def test_*` con `assert` ≈ `@Test` con `assertEquals`.
- En el frontend, la prueba de caja blanca reemplaza la red (`fetch`) por un mock
  (`vi.fn()`), que es el equivalente directo de **Mockito** (`mock()` + `verify()`).
  En el backend, la caja negra usa el `AsyncClient` de FastAPI sobre una BD SQLite
  en memoria (`tests/conftest.py`), evitando así dependencias externas reales.
