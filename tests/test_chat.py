"""Tests de US-12/13/14 (Agente IA): persistencia en BD + aislamiento por usuario.

El agente ADK in-process se reemplaza por un doble (fake) para no consumir cuota
ni requerir credenciales GCP; aquí se prueba el cableado HTTP, la persistencia y
el control de dueño, no la calidad de las respuestas del LLM (eso vive en la eval
del proyecto ulima-agent).
"""

from collections.abc import AsyncGenerator

import pytest_asyncio

from app.core.security import create_access_token
from app.domains.users.models import User
from app.integrations.agent.ulima_agent import get_ulima_agent
from app.main import app
from tests.conftest import make_user


class FakeAgent:
    """Doble del cliente del agente: no llama a GCP, ecoa la pregunta.

    Registra el último `history` recibido para poder verificar que el servicio
    rehidrata la sesión con el historial persistido (US-13).
    """

    def __init__(self) -> None:
        self.last_history: list[tuple[str, str]] | None = None

    async def ensure_session(
        self,
        session_id: str | None,
        user_id: str = "anonymous",
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        self.last_history = history
        return session_id or f"session-for-{user_id}"

    async def ask(self, message: str, session_id: str, user_id: str = "anonymous") -> str:
        return f"respuesta-a:{message}"


@pytest_asyncio.fixture(autouse=True)
async def fake_agent() -> AsyncGenerator[FakeAgent, None]:
    """Inyecta (y expone) una única instancia del agente fake por test."""
    agent = FakeAgent()
    app.dependency_overrides[get_ulima_agent] = lambda: agent
    yield agent
    app.dependency_overrides.pop(get_ulima_agent, None)


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def test_endpoints_requieren_auth(client) -> None:
    """Sin token → 401 en los endpoints de chat."""
    assert (await client.get("/api/v1/chat/conversations")).status_code == 401
    assert (await client.post("/api/v1/chat/conversations", json={})).status_code == 401
    assert (
        await client.post("/api/v1/chat", json={"conversation_id": "x", "message": "hola"})
    ).status_code == 401


async def test_listar_conversaciones_vacio(client, db_session) -> None:
    user = await make_user(db_session)
    resp = await client.get("/api/v1/chat/conversations", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_crear_conversacion(client, db_session) -> None:
    user = await make_user(db_session)
    resp = await client.post(
        "/api/v1/chat/conversations", json={"mode": "courseDifficulty"}, headers=_auth(user)
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Nueva conversación"
    assert body["mode"] == "courseDifficulty"
    assert body["messages"] == []
    assert body["id"]


async def test_enviar_mensaje_persiste_y_deriva_titulo(client, db_session) -> None:
    """CA US-13: el mensaje y la respuesta quedan guardados; el título se deriva."""
    user = await make_user(db_session)
    headers = _auth(user)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()

    resp = await client.post(
        "/api/v1/chat",
        json={"conversation_id": conv["id"], "message": "¿Qué tan difícil es Cálculo I?"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "respuesta-a:¿Qué tan difícil es Cálculo I?"
    assert body["conversation_id"] == conv["id"]

    detail = (
        await client.get(f"/api/v1/chat/conversations/{conv['id']}", headers=headers)
    ).json()
    assert detail["title"] == "¿Qué tan difícil es Cálculo I?"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["last_message"] == "respuesta-a:¿Qué tan difícil es Cálculo I?"


async def test_historial_sobrevive_entre_peticiones(client, db_session) -> None:
    """Los mensajes se acumulan en la BD a lo largo de varias peticiones."""
    user = await make_user(db_session)
    headers = _auth(user)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()

    for msg in ("primera", "segunda"):
        await client.post(
            "/api/v1/chat",
            json={"conversation_id": conv["id"], "message": msg},
            headers=headers,
        )

    detail = (
        await client.get(f"/api/v1/chat/conversations/{conv['id']}", headers=headers)
    ).json()
    assert [m["content"] for m in detail["messages"]] == [
        "primera",
        "respuesta-a:primera",
        "segunda",
        "respuesta-a:segunda",
    ]


async def test_rehidrata_sesion_con_historial(client, db_session, fake_agent: FakeAgent) -> None:
    """Al 2º mensaje, el servicio pasa el historial previo a `ensure_session`.

    Así, si la sesión ADK se perdió (reinicio o conversación reabierta), se siembra
    desde la BD y el agente recupera el contexto que el usuario ve (US-13).
    """
    user = await make_user(db_session)
    headers = _auth(user)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()

    # 1er mensaje: aún no hay historial previo.
    await client.post(
        "/api/v1/chat", json={"conversation_id": conv["id"], "message": "uno"}, headers=headers
    )
    assert fake_agent.last_history == []

    # 2º mensaje: se pasan los turnos previos (user "uno" + respuesta) para sembrar.
    await client.post(
        "/api/v1/chat", json={"conversation_id": conv["id"], "message": "dos"}, headers=headers
    )
    assert fake_agent.last_history == [("user", "uno"), ("assistant", "respuesta-a:uno")]


async def test_enviar_mensaje_a_conversacion_inexistente(client, db_session) -> None:
    user = await make_user(db_session)
    resp = await client.post(
        "/api/v1/chat",
        json={"conversation_id": "no-existe", "message": "hola"},
        headers=_auth(user),
    )
    assert resp.status_code == 404


async def test_mensaje_vacio_es_rechazado(client, db_session) -> None:
    user = await make_user(db_session)
    headers = _auth(user)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()
    resp = await client.post(
        "/api/v1/chat",
        json={"conversation_id": conv["id"], "message": ""},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_eliminar_conversacion(client, db_session) -> None:
    user = await make_user(db_session)
    headers = _auth(user)
    conv = (await client.post("/api/v1/chat/conversations", json={}, headers=headers)).json()

    deleted = await client.delete(f"/api/v1/chat/conversations/{conv['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/chat/conversations", headers=headers)).json() == []
    assert (
        await client.get(f"/api/v1/chat/conversations/{conv['id']}", headers=headers)
    ).status_code == 404


async def test_eliminar_conversacion_inexistente(client, db_session) -> None:
    user = await make_user(db_session)
    resp = await client.delete("/api/v1/chat/conversations/no-existe", headers=_auth(user))
    assert resp.status_code == 404


# --- Aislamiento por usuario (US-13 binding + US-14 ownership) ---


async def _two_users(db_session) -> tuple[User, User]:
    owner = await make_user(
        db_session, email="a@ulima.edu.pe", user_id="00000000-0000-0000-0000-00000000000a"
    )
    other = await make_user(
        db_session, email="b@ulima.edu.pe", user_id="00000000-0000-0000-0000-00000000000b"
    )
    return owner, other


async def test_lista_solo_muestra_las_del_usuario(client, db_session) -> None:
    owner, other = await _two_users(db_session)
    await client.post("/api/v1/chat/conversations", json={}, headers=_auth(owner))

    assert len((await client.get("/api/v1/chat/conversations", headers=_auth(owner))).json()) == 1
    assert (await client.get("/api/v1/chat/conversations", headers=_auth(other))).json() == []


async def test_no_se_puede_ver_conversacion_ajena(client, db_session) -> None:
    owner, other = await _two_users(db_session)
    conv = (
        await client.post("/api/v1/chat/conversations", json={}, headers=_auth(owner))
    ).json()

    resp = await client.get(
        f"/api/v1/chat/conversations/{conv['id']}", headers=_auth(other)
    )
    assert resp.status_code == 404


async def test_no_se_puede_eliminar_conversacion_ajena(client, db_session) -> None:
    owner, other = await _two_users(db_session)
    conv = (
        await client.post("/api/v1/chat/conversations", json={}, headers=_auth(owner))
    ).json()

    resp = await client.delete(
        f"/api/v1/chat/conversations/{conv['id']}", headers=_auth(other)
    )
    assert resp.status_code == 404
    # Sigue existiendo para su dueño.
    assert (
        await client.get(f"/api/v1/chat/conversations/{conv['id']}", headers=_auth(owner))
    ).status_code == 200


async def test_no_se_puede_enviar_mensaje_a_conversacion_ajena(client, db_session) -> None:
    owner, other = await _two_users(db_session)
    conv = (
        await client.post("/api/v1/chat/conversations", json={}, headers=_auth(owner))
    ).json()

    resp = await client.post(
        "/api/v1/chat",
        json={"conversation_id": conv["id"], "message": "intruso"},
        headers=_auth(other),
    )
    assert resp.status_code == 404
