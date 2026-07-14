"""PRUEBA DE CAJA NEGRA — `POST /api/v1/admin/professors` (crear profesor).

Funcionalidad bajo prueba: creación de un profesor por un administrador.
Router: ``app/domains/admin/router.py`` → ``create_professor``.

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
El cuerpo de la petición (`CreateAdminProfessorRequest`) tiene 5 campos:

    1. name        str, obligatorio, largo 2..120
    2. department  str | None, opcional, largo <= 120
    3. degree      str | None, opcional, largo <= 200
    4. bio         str | None, opcional, largo <= 1000
    5. email       str | None, opcional, largo <= 120

Reglas de negocio observables desde afuera:
    - Requiere autenticación (401 sin token) y rol admin (403 si es estudiante).
    - Los 4 campos opcionales pueden omitirse (quedan en null).

------------------------------------------------------------------------------
Tabla de casos (particiones de equivalencia y valores límite)
------------------------------------------------------------------------------
    Caso                                   Entrada relevante            Esperado
    -------------------------------------  ---------------------------  --------
    Todos los campos válidos               name/department/… correctos  201
    Solo `name` (opcionales omitidos)      sin department/degree/…      201
    Sin token                              (sin Authorization)          401
    Rol estudiante                         token de alumno              403
    `name` de 1 char (bajo el mínimo)      name="N"                     422
    `name` en el límite inferior (2)       name="Na"                    201
    `name` en el límite superior (120)     name="N"*120                 201
    `name` excede el límite (121)          name="N"*121                 422
    `name` ausente                         sin `name`                   422
    `department` en el límite (120)        department="D"*120           201
    `department` excede el límite (121)    department="D"*121           422
    `email` excede el límite (121)         email="e"*121                422
"""

import pytest

from app.domains.users.models import UserRole
from tests.conftest import make_user

URL = "/api/v1/admin/professors"
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
    """Profesor válido de referencia; se sobreescriben campos por caso."""
    payload = {
        "name": "Juan Pérez",
        "department": "Ingeniería",
        "degree": "PhD en Sistemas",
        "bio": "Docente de programación.",
        "email": "jperez@ulima.edu.pe",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Partición: entrada completamente válida y opcionales omitidos.
# ---------------------------------------------------------------------------


async def test_crear_profesor_valido_devuelve_201(client, db_session) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL, json=_valid_payload(), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Juan Pérez"
    assert data["department"] == "Ingeniería"


async def test_solo_name_opcionales_omitidos_devuelve_201(client, db_session) -> None:
    """`department`, `degree`, `bio` y `email` son opcionales: omitirlos es válido."""
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL, json={"name": "Ana Torres"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["department"] is None
    assert data["email"] is None


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
# Campo `name`: particiones inválida/válida + valores límite (2..120).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, esperado",
    [
        ("N", 422),          # límite inferior - 1 (1 char) → inválido
        ("Na", 201),         # valor límite inferior (2) → válido
        ("N" * 120, 201),    # valor límite superior (120) → válido
        ("N" * 121, 422),    # límite superior + 1 (121) → inválido
    ],
)
async def test_name_valores_limite(client, db_session, name, esperado) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL, json=_valid_payload(name=name), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == esperado


async def test_falta_name_devuelve_422(client, db_session) -> None:
    """`name` es el único obligatorio: sin él el contrato rechaza con 422."""
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL,
        json={"department": "Ingeniería"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Campos opcionales con tope de longitud: valores límite de `department` y `email`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "department, esperado",
    [
        ("D" * 120, 201),    # valor límite (120) → válido
        ("D" * 121, 422),    # límite + 1 (121) → inválido
    ],
)
async def test_department_valores_limite(client, db_session, department, esperado) -> None:
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL,
        json=_valid_payload(department=department),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == esperado


async def test_email_excede_limite_devuelve_422(client, db_session) -> None:
    """`email` tiene tope de 120 caracteres: 121 → inválido."""
    token = await _admin_token(client, db_session)
    resp = await client.post(
        URL,
        json=_valid_payload(email="e" * 121),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
