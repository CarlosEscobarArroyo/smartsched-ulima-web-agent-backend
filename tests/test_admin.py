"""Tests del panel de administración (US-29/30/31): CRUD de usuarios y stats."""

import pytest

from tests.conftest import make_user
from app.domains.users.models import UserRole

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
    await make_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "alumno@ulima.edu.pe", "password": "Alumno123"},
    )
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------


async def test_stats_requires_auth(client, db_session):
    resp = await client.get("/api/v1/admin/stats")
    assert resp.status_code == 401


async def test_stats_requires_admin_role(client, db_session):
    token = await _student_token(client, db_session)
    resp = await client.get(
        "/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_stats_returns_counts(client, db_session):
    token = await _admin_token(client, db_session)
    await make_user(db_session, email="s2@ulima.edu.pe", user_id="00000000-0000-0000-0000-000000000003")
    resp = await client.get(
        "/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == 2
    assert data["student_count"] == 1
    assert data["admin_count"] == 1


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------


async def test_list_users_requires_admin(client, db_session):
    token = await _student_token(client, db_session)
    resp = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_list_users_ok(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# POST /admin/users
# ---------------------------------------------------------------------------


async def test_create_user_ok(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.post(
        "/api/v1/admin/users",
        json={
            "name": "Nuevo Alumno",
            "email": "nuevo@ulima.edu.pe",
            "password": "SecretPass1",
            "role": "student",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "nuevo@ulima.edu.pe"
    assert data["role"] == "student"


async def test_create_user_duplicate_email(client, db_session):
    token = await _admin_token(client, db_session)
    payload = {
        "name": "Dupe",
        "email": "admin@ulima.edu.pe",
        "password": "SecretPass1",
        "role": "student",
    }
    resp = await client.post(
        "/api/v1/admin/users", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409


async def test_create_user_weak_password(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.post(
        "/api/v1/admin/users",
        json={"name": "Test", "email": "t@ulima.edu.pe", "password": "123", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT /admin/users/{id}
# ---------------------------------------------------------------------------


async def test_update_user_ok(client, db_session):
    token = await _admin_token(client, db_session)
    # Create a user to update
    create_resp = await client.post(
        "/api/v1/admin/users",
        json={"name": "Original", "email": "orig@ulima.edu.pe", "password": "Pass1234", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"name": "Updated", "email": "orig@ulima.edu.pe", "role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    assert resp.json()["role"] == "admin"


async def test_update_user_not_found(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.put(
        "/api/v1/admin/users/nonexistent-id",
        json={"name": "No Existe", "email": "x@ulima.edu.pe", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /admin/users/{id}
# ---------------------------------------------------------------------------


async def test_delete_user_ok(client, db_session):
    token = await _admin_token(client, db_session)
    create_resp = await client.post(
        "/api/v1/admin/users",
        json={"name": "ToDelete", "email": "del@ulima.edu.pe", "password": "Pass1234", "role": "student"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


async def test_delete_own_account_forbidden(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.delete(
        f"/api/v1/admin/users/{ADMIN_UUID}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


async def test_delete_user_not_found(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.delete(
        "/api/v1/admin/users/ghost-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Professors
# ---------------------------------------------------------------------------


async def test_list_professors_empty(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.get("/api/v1/admin/professors", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_professor_ok(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.post(
        "/api/v1/admin/professors",
        json={"name": "Dr. García López"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Dr. García López"
    assert data["initials"] == "GL"
    assert data["review_count"] == 0
    assert "id" in data


async def test_create_professor_short_name(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.post(
        "/api/v1/admin/professors",
        json={"name": "X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_update_professor_ok(client, db_session):
    token = await _admin_token(client, db_session)
    create = await client.post(
        "/api/v1/admin/professors",
        json={"name": "Prof Original"},
        headers={"Authorization": f"Bearer {token}"},
    )
    prof_id = create.json()["id"]
    resp = await client.put(
        f"/api/v1/admin/professors/{prof_id}",
        json={"name": "Prof Actualizado"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Prof Actualizado"


async def test_update_professor_not_found(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.put(
        "/api/v1/admin/professors/ghost-id",
        json={"name": "No Existe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_delete_professor_ok(client, db_session):
    token = await _admin_token(client, db_session)
    create = await client.post(
        "/api/v1/admin/professors",
        json={"name": "Para Borrar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    prof_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/admin/professors/{prof_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


async def test_delete_professor_not_found(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.delete(
        "/api/v1/admin/professors/ghost-id", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


async def test_list_courses_empty(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.get("/api/v1/admin/courses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_course_ok(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.post(
        "/api/v1/admin/courses",
        json={"code": "CS101", "name": "Programación I", "level": "1", "prerequisites": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "CS101"
    assert data["name"] == "Programación I"
    assert data["level"] == "1"
    assert data["prerequisites"] == []
    assert data["professor_id"] is None
    assert data["professor_name"] is None


async def test_create_course_duplicate_code(client, db_session):
    token = await _admin_token(client, db_session)
    payload = {"code": "CS101", "name": "Prog I", "level": "1", "prerequisites": []}
    await client.post(
        "/api/v1/admin/courses", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    resp = await client.post(
        "/api/v1/admin/courses", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409


async def test_update_course_ok(client, db_session):
    token = await _admin_token(client, db_session)
    create = await client.post(
        "/api/v1/admin/courses",
        json={"code": "MAT101", "name": "Cálculo I", "level": "1", "prerequisites": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    course_id = create.json()["id"]
    resp = await client.put(
        f"/api/v1/admin/courses/{course_id}",
        json={"code": "MAT101", "name": "Cálculo I Actualizado", "level": "2", "prerequisites": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Cálculo I Actualizado"
    assert resp.json()["level"] == "2"


async def test_update_course_not_found(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.put(
        "/api/v1/admin/courses/ghost-id",
        json={"code": "XX999", "name": "No existe", "level": "1", "prerequisites": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_delete_course_ok(client, db_session):
    token = await _admin_token(client, db_session)
    create = await client.post(
        "/api/v1/admin/courses",
        json={"code": "DEL101", "name": "Para Borrar", "level": "1", "prerequisites": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    course_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/admin/courses/{course_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


async def test_delete_course_not_found(client, db_session):
    token = await _admin_token(client, db_session)
    resp = await client.delete(
        "/api/v1/admin/courses/ghost-id", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


async def test_create_course_with_professor(client, db_session):
    token = await _admin_token(client, db_session)
    # Create a professor first
    prof_resp = await client.post(
        "/api/v1/admin/professors",
        json={"name": "Dr. Prueba"},
        headers={"Authorization": f"Bearer {token}"},
    )
    prof_id = prof_resp.json()["id"]

    resp = await client.post(
        "/api/v1/admin/courses",
        json={"code": "TP101", "name": "Test", "level": "1", "prerequisites": [], "professor_id": prof_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["professor_id"] == prof_id
    assert data["professor_name"] == "Dr. Prueba"
