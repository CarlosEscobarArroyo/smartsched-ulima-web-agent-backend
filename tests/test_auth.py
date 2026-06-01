"""Tests de autenticación (US-24): login, bloqueo, token y roles."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.domains.auth.deps import require_role
from app.domains.users.models import User, UserRole
from tests.conftest import make_user


async def test_login_success(client, db_session):
    """CA-1: credenciales válidas → 200 con token y usuario."""
    await make_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"] == {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "alumno@ulima.edu.pe",
        "name": "Alumno Demo",
        "role": "student",
    }


async def test_login_wrong_password(client, db_session):
    """Contraseña incorrecta → 401."""
    await make_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "malísima"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client, db_session):
    """Email inexistente → 401 (no revela existencia)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nadie@ulima.edu.pe", "password": "Whatever1"},
    )
    assert resp.status_code == 401


async def test_lockout_after_three_attempts(client, db_session):
    """CA-2: 3 intentos fallidos → bloqueo (423), incluso con contraseña correcta."""
    await make_user(db_session)
    for _ in range(2):
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "alumno@ulima.edu.pe", "password": "mala"},
        )
        assert r.status_code == 401

    # Tercer fallo dispara el bloqueo.
    r3 = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "mala"},
    )
    assert r3.status_code == 423

    # Aún con la contraseña correcta, sigue bloqueada.
    r4 = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    assert r4.status_code == 423


async def test_expired_lockout_allows_login(client, db_session):
    """Un bloqueo vencido permite volver a entrar con credenciales válidas."""
    user = await make_user(db_session)
    user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    assert resp.status_code == 200


async def test_me_requires_token(client, db_session):
    """GET /auth/me sin token → 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_token(client, db_session):
    """Login → token → GET /auth/me devuelve el usuario."""
    await make_user(db_session)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    token = login.json()["access_token"]
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "00000000-0000-0000-0000-000000000001"


async def test_me_with_invalid_token(client, db_session):
    """Token inválido → 401."""
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer no-es-un-jwt"}
    )
    assert resp.status_code == 401


async def test_require_role_allows_matching_role():
    """require_role deja pasar al rol correcto."""
    admin = User(
        id="adm-001",
        email="admin@ulima.edu.pe",
        name="Admin",
        password_hash="x",
        role=UserRole.ADMIN.value,
    )
    checker = require_role(UserRole.ADMIN)
    assert await checker(current=admin) is admin


async def test_require_role_rejects_other_role():
    """require_role rechaza (403) a un rol distinto."""
    student = User(
        id="stu-001",
        email="alumno@ulima.edu.pe",
        name="Alumno",
        password_hash="x",
        role=UserRole.STUDENT.value,
    )
    checker = require_role(UserRole.ADMIN)
    with pytest.raises(HTTPException) as exc:
        await checker(current=student)
    assert exc.value.status_code == 403
