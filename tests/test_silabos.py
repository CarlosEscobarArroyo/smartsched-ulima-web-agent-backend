"""Tests de la descarga pública del sílabo (GET /api/v1/silabos/{id}) — GCS mockeado."""

from app.domains.users.models import UserRole
from tests.conftest import make_user

ADMIN_UUID = "00000000-0000-0000-0000-000000000009"


async def _admin_token(client, db_session) -> str:
    await make_user(
        db_session,
        email="admin@ulima.edu.pe",
        password="Admin1234",
        name="Admin",
        role=UserRole.ADMIN,
        user_id=ADMIN_UUID,
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "admin@ulima.edu.pe", "password": "Admin1234"}
    )
    return resp.json()["access_token"]


async def _create_course(client, token, code="SIL1") -> str:
    resp = await client.post(
        "/api/v1/admin/courses",
        json={"code": code, "name": "Curso", "level": "1", "prerequisites": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


async def test_download_silabo_publico_ok(client, db_session, monkeypatch):
    from app.integrations.bucket import bucket

    monkeypatch.setattr(bucket, "upload_syllabus", lambda *a, **k: "gs://b/syllabi/x.pdf")
    monkeypatch.setattr(
        bucket, "download_from_gcs", lambda p: (b"%PDF bytes", "application/pdf")
    )
    token = await _admin_token(client, db_session)
    course_id = await _create_course(client, token)
    await client.post(
        f"/api/v1/admin/courses/{course_id}/syllabus",
        files={"file": ("silabo.pdf", b"%PDF x", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Sin Authorization: la ruta es pública (para abrir desde el chat).
    resp = await client.get(f"/api/v1/silabos/{course_id}")
    assert resp.status_code == 200
    assert resp.content == b"%PDF bytes"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert "silabo.pdf" in resp.headers["content-disposition"]


async def test_download_silabo_sin_silabo_404(client, db_session):
    token = await _admin_token(client, db_session)
    course_id = await _create_course(client, token, code="SIL2")
    resp = await client.get(f"/api/v1/silabos/{course_id}")
    assert resp.status_code == 404


async def test_download_silabo_curso_inexistente_404(client, db_session):
    resp = await client.get("/api/v1/silabos/ghost-id")
    assert resp.status_code == 404
