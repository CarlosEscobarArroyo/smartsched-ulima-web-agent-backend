"""Cliente hacia el agente Vertex AI / google-adk.

Por ahora es un stub. La integración real con `ulima-agent` (google-cloud-aiplatform
agent_engines) se conecta cuando se desplegue el agente.
"""

from app.core.config import get_settings


class UlimaAgentClient:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def ask(self, message: str, session_id: str | None = None) -> str:
        # TODO: reemplazar por llamada real al agente desplegado en Vertex AI
        return f"[stub:{self._settings.environment}] recibí: {message}"


def get_ulima_agent() -> UlimaAgentClient:
    return UlimaAgentClient()
