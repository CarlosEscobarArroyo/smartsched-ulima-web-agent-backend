"""Tests de profesores y reseñas (US-21)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin import repository as admin_repo
from tests.conftest import make_user


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_professor(db: AsyncSession, name: str = "García López") -> str:
    p = await admin_repo.create_professor(db, name=name)
    return p.id


@pytest.mark.asyncio
async def test_list_professors_empty(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.get("/api/v1/professors")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_professors_con_datos(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_professor(db_session, "Dr. García López")
    resp = await client.get("/api/v1/professors")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    p = data[0]
    assert p["name"] == "Dr. García López"
    assert p["initials"] == "GL"
    assert p["availability"] == []
    assert p["reviews"] == []
    assert p["rating"] == 0.0
    assert p["courses"] == []


@pytest.mark.asyncio
async def test_add_review_sin_token(client: AsyncClient, db_session: AsyncSession) -> None:
    prof_id = await _create_professor(db_session)
    resp = await client.post(
        f"/api/v1/professors/{prof_id}/reviews", json={"rating": 4, "comment": "Muy bueno"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_review_ok(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session)
    token = await _login(client, "alumno@ulima.edu.pe", "Alumno123")
    prof_id = await _create_professor(db_session)

    resp = await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 5, "comment": "Excelente profesor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    review = resp.json()
    assert review["rating"] == 5
    assert review["comment"] == "Excelente profesor"
    assert review["student"] == "Alumno Demo"
    assert "id" in review
    assert "date" in review


@pytest.mark.asyncio
async def test_add_review_sin_comentario(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session)
    token = await _login(client, "alumno@ulima.edu.pe", "Alumno123")
    prof_id = await _create_professor(db_session)

    resp = await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["comment"] == ""


@pytest.mark.asyncio
async def test_add_review_duplicado(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session)
    token = await _login(client, "alumno@ulima.edu.pe", "Alumno123")
    prof_id = await _create_professor(db_session)

    await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_review_profesor_no_encontrado(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session)
    token = await _login(client, "alumno@ulima.edu.pe", "Alumno123")

    resp = await client.post(
        "/api/v1/professors/00000000-0000-0000-0000-000000000099/reviews",
        json={"rating": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_review_rating_invalido(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session)
    token = await _login(client, "alumno@ulima.edu.pe", "Alumno123")
    prof_id = await _create_professor(db_session)

    resp = await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 6},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_professors_muestra_reviews(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session)
    token = await _login(client, "alumno@ulima.edu.pe", "Alumno123")
    prof_id = await _create_professor(db_session, "Martínez Silva")

    await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 4, "comment": "Buena didáctica"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get("/api/v1/professors")
    assert resp.status_code == 200
    prof = resp.json()[0]
    assert prof["rating"] == 4.0
    assert len(prof["reviews"]) == 1
    assert prof["reviews"][0]["student"] == "Alumno Demo"
    assert prof["reviews"][0]["comment"] == "Buena didáctica"


@pytest.mark.asyncio
async def test_dos_usuarios_pueden_reseniar_mismo_profesor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, email="alumno@ulima.edu.pe", user_id="00000000-0000-0000-0000-000000000001")
    await make_user(
        db_session,
        email="otro@ulima.edu.pe",
        user_id="00000000-0000-0000-0000-000000000002",
        name="Otro Alumno",
    )
    token1 = await _login(client, "alumno@ulima.edu.pe", "Alumno123")
    token2 = await _login(client, "otro@ulima.edu.pe", "Alumno123")
    prof_id = await _create_professor(db_session)

    r1 = await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 5},
        headers={"Authorization": f"Bearer {token1}"},
    )
    r2 = await client.post(
        f"/api/v1/professors/{prof_id}/reviews",
        json={"rating": 3},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201

    resp = await client.get("/api/v1/professors")
    prof = resp.json()[0]
    assert len(prof["reviews"]) == 2
    assert prof["rating"] == 4.0
