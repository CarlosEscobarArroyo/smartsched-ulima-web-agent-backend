"""Tests del módulo de soporte (Configuración → Contactar soporte)."""

from sqlalchemy import select

from app.domains.support.models import SupportMessage
from tests.conftest import make_user


async def _student_token(client, db_session) -> str:
    await make_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    return resp.json()["access_token"]


async def test_contact_requires_auth(client, db_session):
    resp = await client.post(
        "/api/v1/support/contact",
        json={"email": "alumno@ulima.edu.pe", "message": "Necesito ayuda con mi horario."},
    )
    assert resp.status_code == 401


async def test_contact_persiste_mensaje(client, db_session):
    token = await _student_token(client, db_session)
    resp = await client.post(
        "/api/v1/support/contact",
        json={"email": "alumno@ulima.edu.pe", "message": "Necesito ayuda con mi horario."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alumno@ulima.edu.pe"
    assert data["message"] == "Necesito ayuda con mi horario."
    assert "id" in data and "created_at" in data

    stored = await db_session.scalar(
        select(SupportMessage).where(SupportMessage.id == data["id"])
    )
    assert stored is not None
    assert stored.message == "Necesito ayuda con mi horario."


async def test_contact_mensaje_corto_rechazado(client, db_session):
    token = await _student_token(client, db_session)
    resp = await client.post(
        "/api/v1/support/contact",
        json={"email": "alumno@ulima.edu.pe", "message": "corto"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_contact_email_invalido_rechazado(client, db_session):
    token = await _student_token(client, db_session)
    resp = await client.post(
        "/api/v1/support/contact",
        json={"email": "no-es-un-correo", "message": "Necesito ayuda con mi horario."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
