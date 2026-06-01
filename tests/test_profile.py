"""Tests de modificación de perfil (US-26): PATCH /api/v1/auth/me."""

from tests.conftest import make_user

ME_URL = "/api/v1/auth/me"
LOGIN_URL = "/api/v1/auth/login"


async def _token(client, email: str = "alumno@ulima.edu.pe", password: str = "Alumno123") -> str:
    resp = await client.post(LOGIN_URL, json={"email": email, "password": password})
    return resp.json()["access_token"]


async def test_update_me_name_ok(client, db_session):
    """Cambiar nombre → 200, nombre actualizado."""
    await make_user(db_session)
    token = await _token(client)
    resp = await client.patch(
        ME_URL,
        json={"name": "Nuevo Nombre", "email": "alumno@ulima.edu.pe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nuevo Nombre"


async def test_update_me_email_ok(client, db_session):
    """Cambiar email a uno libre → 200, email actualizado."""
    await make_user(db_session)
    token = await _token(client)
    resp = await client.patch(
        ME_URL,
        json={"name": "Alumno Demo", "email": "nuevo@ulima.edu.pe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "nuevo@ulima.edu.pe"


async def test_update_me_same_email_ok(client, db_session):
    """Enviar el mismo email propio no genera conflicto → 200."""
    await make_user(db_session)
    token = await _token(client)
    resp = await client.patch(
        ME_URL,
        json={"name": "Nuevo Nombre", "email": "alumno@ulima.edu.pe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_update_me_email_conflict(client, db_session):
    """Email ya en uso por otro usuario → 409."""
    await make_user(db_session, email="otro@ulima.edu.pe", user_id="00000000-0000-0000-0000-000000000002")
    await make_user(db_session)
    token = await _token(client)
    resp = await client.patch(
        ME_URL,
        json={"name": "Alumno Demo", "email": "otro@ulima.edu.pe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


async def test_update_me_no_token(client, db_session):
    """Sin token → 401."""
    resp = await client.patch(ME_URL, json={"name": "X", "email": "x@x.com"})
    assert resp.status_code == 401


async def test_update_me_name_too_short(client, db_session):
    """Nombre de 1 carácter → 422."""
    await make_user(db_session)
    token = await _token(client)
    resp = await client.patch(
        ME_URL,
        json={"name": "X", "email": "alumno@ulima.edu.pe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_update_me_invalid_email(client, db_session):
    """Email malformado → 422."""
    await make_user(db_session)
    token = await _token(client)
    resp = await client.patch(
        ME_URL,
        json={"name": "Alumno Demo", "email": "no-es-un-email"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
