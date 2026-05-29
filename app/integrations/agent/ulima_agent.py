"""Cliente del Agente IA (US-12), corriendo *in-process* en el backend.

El agente vive en el proyecto ADK embebido `ulima-agent/` (paquete `ulima_agent`)
y se ejecuta dentro de este proceso con `InMemoryRunner.run_async` — sin llamar a
un servicio remoto. El runner y sus sesiones son in-memory (efímeros), consistente
con la fase actual de US-12 (sin auth ni persistencia).

El import de ADK y del agente es perezoso para que importar este módulo no requiera
credenciales GCP (las pruebas que no usan el agente pueden mockear este cliente).
"""

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

APP_NAME = "ulima_agent"
ANONYMOUS_USER_ID = "anonymous"


def _event_text(event: Any) -> str:
    """Extrae el texto de un evento ADK, ignorando 'thoughts'."""
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) if content else None
    if not parts:
        return ""
    return "".join(
        part.text
        for part in parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    )


class UlimaAgentClient:
    """Envuelve el `InMemoryRunner` del agente. Singleton ligero por proceso."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._runner: Any | None = None

    def _get_runner(self) -> Any:
        if self._runner is None:
            from google.adk.runners import InMemoryRunner
            from ulima_agent.agent import root_agent

            self._runner = InMemoryRunner(app_name=APP_NAME, agent=root_agent)
        return self._runner

    async def create_session(self, user_id: str = ANONYMOUS_USER_ID) -> str:
        """Crea una sesión ADK in-memory y devuelve su id."""
        runner = self._get_runner()
        session = await runner.session_service.create_session(
            app_name=APP_NAME, user_id=user_id
        )
        return session.id

    async def ask(
        self,
        message: str,
        session_id: str,
        user_id: str = ANONYMOUS_USER_ID,
    ) -> str:
        """Envía un mensaje al agente en la sesión dada y devuelve su respuesta."""
        from google.genai import types

        runner = self._get_runner()
        content = types.Content(role="user", parts=[types.Part(text=message)])

        try:
            reply = ""
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content
            ):
                text = _event_text(event)
                if text:
                    reply = text
            return reply or "El agente no devolvió respuesta. Intenta reformular tu consulta."
        except Exception:
            logger.exception("Error al consultar al agente (Vertex AI)")
            return (
                "Lo siento, hubo un problema al contactar al Agente IA. "
                "Intenta nuevamente en unos momentos."
            )


def get_ulima_agent() -> UlimaAgentClient:
    return _agent_client


_agent_client = UlimaAgentClient()
