"""Tests de US-12 (Agente IA): store in-memory + endpoints de chat/conversaciones.

El agente ADK in-process se reemplaza por un doble (fake) para no consumir cuota
ni requerir credenciales GCP; aquí se prueba el cableado HTTP y el store, no la
calidad de las respuestas del LLM (eso vive en la eval del proyecto ulima-agent).
"""

import pytest
from fastapi.testclient import TestClient

from app.domains.chat.router import get_chat_service
from app.domains.chat.service import ChatService
from app.domains.chat.store import ConversationStore
from app.main import app


class FakeAgent:
    def __init__(self) -> None:
        self.sessions = 0

    async def create_session(self, user_id: str = "anonymous") -> str:
        self.sessions += 1
        return f"session-{self.sessions}"

    async def ask(self, message: str, session_id: str, user_id: str = "anonymous") -> str:
        return f"respuesta-a:{message}"


@pytest.fixture
def client() -> TestClient:
    store = ConversationStore()
    agent = FakeAgent()
    app.dependency_overrides[get_chat_service] = lambda: ChatService(agent=agent, store=store)
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_listar_conversaciones_vacio(client: TestClient) -> None:
    response = client.get("/api/v1/chat/conversations")
    assert response.status_code == 200
    assert response.json() == []


def test_crear_conversacion(client: TestClient) -> None:
    response = client.post("/api/v1/chat/conversations", json={"mode": "courseDifficulty"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Nueva conversación"
    assert body["mode"] == "courseDifficulty"
    assert body["messages"] == []
    assert body["id"]


def test_enviar_mensaje_y_recibir_respuesta(client: TestClient) -> None:
    conv = client.post("/api/v1/chat/conversations", json={}).json()
    response = client.post(
        "/api/v1/chat",
        json={"conversation_id": conv["id"], "message": "¿Qué tan difícil es Cálculo I?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "respuesta-a:¿Qué tan difícil es Cálculo I?"
    assert body["conversation_id"] == conv["id"]

    # El detalle de la conversación acumula los mensajes y deriva el título.
    detail = client.get(f"/api/v1/chat/conversations/{conv['id']}").json()
    assert detail["title"] == "¿Qué tan difícil es Cálculo I?"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["last_message"] == "respuesta-a:¿Qué tan difícil es Cálculo I?"


def test_enviar_mensaje_a_conversacion_inexistente(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat",
        json={"conversation_id": "no-existe", "message": "hola"},
    )
    assert response.status_code == 404


def test_mensaje_vacio_es_rechazado(client: TestClient) -> None:
    conv = client.post("/api/v1/chat/conversations", json={}).json()
    response = client.post(
        "/api/v1/chat",
        json={"conversation_id": conv["id"], "message": ""},
    )
    assert response.status_code == 422


def test_eliminar_conversacion(client: TestClient) -> None:
    conv = client.post("/api/v1/chat/conversations", json={}).json()
    delete = client.delete(f"/api/v1/chat/conversations/{conv['id']}")
    assert delete.status_code == 204
    # Ya no aparece en la lista ni en el detalle.
    assert client.get("/api/v1/chat/conversations").json() == []
    assert client.get(f"/api/v1/chat/conversations/{conv['id']}").status_code == 404


def test_eliminar_conversacion_inexistente(client: TestClient) -> None:
    assert client.delete("/api/v1/chat/conversations/no-existe").status_code == 404


def test_store_ordena_por_actualizacion() -> None:
    store = ConversationStore()
    first = store.create()
    second = store.create()
    store.add_message(first.id, "user", "hola")  # actualiza 'first'
    listed = store.list()
    assert listed[0].id == first.id
    assert listed[1].id == second.id
