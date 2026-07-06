"""PRUEBA DE CAJA NEGRA — `POST /api/v1/admin/courses` (crear curso).

Funcionalidad bajo prueba: creación de un curso por un administrador.
Router: ``app/domains/admin/router.py`` → ``create_course``.

------------------------------------------------------------------------------
¿Por qué caja negra?
------------------------------------------------------------------------------
La caja negra prueba la funcionalidad SIN mirar el código interno: solo importan
las ENTRADAS y las SALIDAS esperadas (contrato). Se diseñan los casos con
"particiones de equivalencia" (agrupar entradas que se comportan igual) y
"valores límite" (los bordes de cada partición).

------------------------------------------------------------------------------
Campos de entrada (5 > 4 requeridos por el criterio)
------------------------------------------------------------------------------
El cuerpo de la petición (`CreateAdminCourseRequest`) tiene 5 campos:

    1. code           str, obligatorio, largo 1..20
    2. name           str, obligatorio, largo 1..120
    3. level          str, obligatorio, largo 1..10
    4. prerequisites  list[str], opcional (por defecto [])
    5. professor_id   str | None, opcional

Además la funcionalidad tiene reglas de negocio observables desde afuera:
    - Requiere autenticación (401 sin token) y rol admin (403 si es estudiante).
    - El `code` se normaliza a mayúsculas y debe ser único (409 si se repite).

------------------------------------------------------------------------------
Tabla de casos (particiones de equivalencia y valores límite)
------------------------------------------------------------------------------
    Caso                                   Entrada relevante            Esperado
    -------------------------------------  ---------------------------  --------
    Todos los campos válidos               code/name/level correctos    201
    Sin token                              (sin Authorization)          401
    Rol estudiante                         token de alumno              403
    `code` vacío                           code=""                      422
    `code` en el límite (20 chars)         code="C"*20                  201
    `code` excede el límite (21 chars)     code="C"*21                  422
    `name` vacío                           name=""                      422
    `name` en el límite (120 chars)        name="N"*120                 201
    `level` vacío                          level=""                     422
    Falta un campo obligatorio             sin `name`                   422
    `code` duplicado (case-insensitive)    "cs101" y luego "CS101"      409
    Opcionales omitidos                    sin prerequisites/professor  201
"""

import pytest

from app.domains.users.models import UserRole
from tests.conftest import make_user

URL = "/api/v1/admin/courses"
ADMIN_UUID = "00000000-0000-0000-0000-000000000002"


async def _admin_token(client, db_session) -> str:
    await make_user(
        db_session,
        email="admin@ulima.edu.pe",
        password="Admin1234",
        name="Admin Demo",
        role=UserRole.ADMIN,
        user_id=ADMIN_UUID,
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ulima.edu.pe", "password": "Admin1234"},
    )
    return resp.json()["access_token"]


async def _student_token(client, db_session) -> str:
    await make_user(db_session)  # alumno por defecto (conftest)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    return resp.json()["access_token"]


def _valid_payload(**overrides) -> dict:
    """Curso válido de referencia; se sobreescriben campos por caso."""
    payload = {"code": "CS101", "name": "Programación I", "level": "1", "prerequisites": []}
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Partición: entrada completamente válida.
# ---------------------------------------------------------------------------


async def test_crear_curso_valido_devuelve_201(client, db_session) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL, json=_valid_payload(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "CS101"
    assert data["name"] == "Programación I"
    assert data["level"] == "1"


async def test_opcionales_omitidos_devuelve_201(client, db_session) -> None:
    """`prerequisites` y `professor_id` son opcionales: omitirlos es válido."""
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL,
        json={"code": "CS102", "name": "Programación II", "level": "2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["prerequisites"] == []
    assert resp.json()["professor_id"] is None


# ---------------------------------------------------------------------------
# Partición: autorización (reglas de negocio observables).
# ---------------------------------------------------------------------------


async def test_sin_token_devuelve_401(client, db_session) -> None:
    resp = await client.post(URL, json=_valid_payload())
    assert resp.status_code == 401


async def test_rol_estudiante_devuelve_403(client, db_session) -> None:
    token = await _student_token(client, db_session)
    resp = await client.post(
        URL, json=_valid_payload(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Campo `code`: particiones inválida/válida + valores límite (1..20).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code, esperado",
    [
        ("", 422),          # límite inferior - 1 (vacío) → inválido
        ("C" * 20, 201),    # valor límite superior (20) → válido
        ("C" * 21, 422),    # límite superior + 1 (21) → inválido
    ],
)
async def test_code_valores_limite(client, db_session, code, esperado) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL, json=_valid_payload(code=code), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == esperado


# ---------------------------------------------------------------------------
# Campo `name`: vacío (inválido) vs. límite superior 120 (válido).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, esperado",
    [
        ("", 422),          # vacío → inválido
        ("N" * 120, 201),   # valor límite (120) → válido
    ],
)
async def test_name_valores_limite(client, db_session, name, esperado) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL,
        json=_valid_payload(code="NM100", name=name),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == esperado


# ---------------------------------------------------------------------------
# Campo `level` vacío y campo obligatorio ausente → 422.
# ---------------------------------------------------------------------------


async def test_level_vacio_devuelve_422(client, db_session) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL, json=_valid_payload(level=""), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


async def test_falta_campo_obligatorio_devuelve_422(client, db_session) -> None:
    """Falta `name` (obligatorio) → el contrato lo rechaza con 422."""
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL,
        json={"code": "NO100", "level": "1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Regla de negocio: `code` único (normalizado a mayúsculas) → 409.
# ---------------------------------------------------------------------------


async def test_code_duplicado_ignora_mayusculas_devuelve_409(client, db_session) -> None:
    token = await _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    primera = await client.post(URL, json=_valid_payload(code="cs101"), headers=headers)
    assert primera.status_code == 201  # se guarda como "CS101"
    segunda = await client.post(URL, json=_valid_payload(code="CS101"), headers=headers)
    assert segunda.status_code == 409
