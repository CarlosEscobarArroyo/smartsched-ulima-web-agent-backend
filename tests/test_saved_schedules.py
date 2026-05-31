"""Tests de US-09: guardar / listar / eliminar horarios (saved_schedules)."""

from app.core.security import create_access_token
from app.domains.users.models import User
from tests.conftest import make_user

SAMPLE = {"name": "Mi horario", "schedule_data": {"id": "opt-1", "courses": []}}


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def test_save_requires_auth(client, db_session):
    """Sin token → 401."""
    resp = await client.post("/api/v1/schedules/saved", json=SAMPLE)
    assert resp.status_code == 401


async def test_save_and_list(client, db_session):
    """CA-1: guardar con nombre → aparece en la lista del usuario."""
    user = await make_user(db_session)
    headers = _auth(user)

    created = await client.post("/api/v1/schedules/saved", json=SAMPLE, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Mi horario"
    assert body["id"]
    assert body["savedAt"]
    assert "schedule_data" not in body  # el shape del FE es {id, name, savedAt}

    listed = await client.get("/api/v1/schedules/saved", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_get_detail_includes_blob(client, db_session):
    """El detalle SÍ expone `scheduleData` (la lista no), para re-renderizar."""
    user = await make_user(db_session)
    headers = _auth(user)
    blob = {"id": "opt-1", "courses": [{"code": "INF101", "name": "Algoritmos"}]}
    created = (
        await client.post(
            "/api/v1/schedules/saved",
            json={"name": "Con detalle", "schedule_data": blob},
            headers=headers,
        )
    ).json()

    detail = await client.get(
        f"/api/v1/schedules/saved/{created['id']}", headers=headers
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Con detalle"
    assert body["savedAt"]
    assert body["scheduleData"] == blob  # camelCase, con el blob completo


async def test_get_detail_not_owned_returns_404(client, db_session):
    """No se puede ver el detalle del horario de otro usuario → 404."""
    owner = await make_user(db_session, email="a@ulima.edu.pe", user_id="u-a")
    other = await make_user(db_session, email="b@ulima.edu.pe", user_id="u-b")
    created = (
        await client.post("/api/v1/schedules/saved", json=SAMPLE, headers=_auth(owner))
    ).json()

    resp = await client.get(
        f"/api/v1/schedules/saved/{created['id']}", headers=_auth(other)
    )
    assert resp.status_code == 404


async def test_get_detail_requires_auth(client, db_session):
    """Sin token → 401."""
    resp = await client.get("/api/v1/schedules/saved/whatever")
    assert resp.status_code == 401


async def test_delete(client, db_session):
    """Eliminar un horario propio → 204 y desaparece de la lista."""
    user = await make_user(db_session)
    headers = _auth(user)
    created = (
        await client.post("/api/v1/schedules/saved", json=SAMPLE, headers=headers)
    ).json()

    deleted = await client.delete(
        f"/api/v1/schedules/saved/{created['id']}", headers=headers
    )
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/schedules/saved", headers=headers)
    assert listed.json() == []


async def test_delete_not_owned_returns_404(client, db_session):
    """No se puede borrar el horario de otro usuario → 404."""
    owner = await make_user(db_session, email="a@ulima.edu.pe", user_id="u-a")
    other = await make_user(db_session, email="b@ulima.edu.pe", user_id="u-b")
    created = (
        await client.post("/api/v1/schedules/saved", json=SAMPLE, headers=_auth(owner))
    ).json()

    resp = await client.delete(
        f"/api/v1/schedules/saved/{created['id']}", headers=_auth(other)
    )
    assert resp.status_code == 404


async def test_limit_of_ten(client, db_session):
    """El 11º guardado → 409 (tope de 10 por usuario)."""
    user = await make_user(db_session)
    headers = _auth(user)
    for i in range(10):
        r = await client.post(
            "/api/v1/schedules/saved",
            json={"name": f"Horario {i}", "schedule_data": {}},
            headers=headers,
        )
        assert r.status_code == 201

    overflow = await client.post(
        "/api/v1/schedules/saved",
        json={"name": "Horario 11", "schedule_data": {}},
        headers=headers,
    )
    assert overflow.status_code == 409
