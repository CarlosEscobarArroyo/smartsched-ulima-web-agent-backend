"""Cliente del Agente IA (US-12), corriendo *in-process* en el backend.

El agente vive en el proyecto ADK embebido `ulima-agent/` (paquete `ulima_agent`)
y se ejecuta dentro de este proceso con `InMemoryRunner.run_async` — sin llamar a
un servicio remoto. El runner y sus sesiones son in-memory (efímeros), consistente
con la fase actual de US-12 (sin auth ni persistencia).

El import de ADK y del agente es perezoso para que importar este módulo no requiera
credenciales GCP (las pruebas que no usan el agente pueden mockear este cliente).
"""

import logging
import os
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


# Tools que generan una ficha visual (one page). Su URL se asegura en el texto de la
# respuesta para que el frontend la renderice como tarjeta embebida y se persista junto
# al mensaje (así sobrevive a recargar la conversación). Ver ulima_agent/tools/fichas.py.
_FICHA_TOOLS = {"generar_ficha_curso", "generar_ficha_profesor"}


def _ficha_urls_from_event(event: Any) -> list[str]:
    """URLs de ficha presentes en las function-responses de un evento ADK."""
    urls: list[str] = []
    try:
        responses = event.get_function_responses()
    except Exception:
        return urls
    for fr in responses or []:
        if getattr(fr, "name", None) not in _FICHA_TOOLS:
            continue
        resp = getattr(fr, "response", None)
        if isinstance(resp, dict) and resp.get("url"):
            urls.append(str(resp["url"]))
    return urls


def _ensure_ficha_urls(reply: str, urls: list[str]) -> str:
    """Garantiza que cada URL de ficha aparezca en el texto (sin duplicar).

    No dependemos de que el LLM repita la URL: si no está en su respuesta, la añadimos.
    El frontend detecta estas URLs y muestra la ficha como tarjeta dentro del chat.
    """
    for url in dict.fromkeys(urls):  # dedup preservando orden
        if url and url not in reply:
            reply = f"{reply}\n\n{url}" if reply else url
    return reply


class UlimaAgentClient:
    """Facade (estructural) sobre el subsistema de ADK.

    Expone una interfaz simple (`create_session`/`ensure_session`/`ask`) y esconde
    todo el subsistema: `InMemoryRunner`, `session_service`, `Event`, `types.Content`,
    el bucle `run_async` y la rehidratación de historial. La única instancia por
    proceso (Singleton) se crea abajo como `_agent_client`.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        # Puente settings -> entorno: las tools del agente (paquete `ulima_agent`,
        # que NO importa `app`) leen DATABASE_URL de os.environ para consultar Neon.
        # En Cloud Run ya es una env var real; en local viene de .env vía
        # pydantic-settings, que no la exporta, así que la exponemos aquí.
        # setdefault: una env var real (Cloud Run) siempre gana.
        if self._settings.database_url:
            os.environ.setdefault("DATABASE_URL", self._settings.database_url)
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

    async def ensure_session(
        self,
        session_id: str | None,
        user_id: str = ANONYMOUS_USER_ID,
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        """Devuelve un session_id ADK válido, creando uno nuevo si hace falta.

        Las sesiones del runner son in-memory: tras reiniciar el backend (o al
        reabrir una conversación antigua), el `adk_session_id` guardado queda
        obsoleto. Aquí se revalida contra el runner; si ya no existe, se crea una
        sesión nueva y se **rehidrata con el historial persistido** (`history` =
        lista de `(role, content)` en orden), para que el agente recupere el
        contexto que el usuario sí ve en pantalla (US-13). Si la sesión sigue
        viva, se reutiliza tal cual (no se siembra → no se duplica).
        """
        runner = self._get_runner()
        if session_id:
            try:
                existing = await runner.session_service.get_session(
                    app_name=APP_NAME, user_id=user_id, session_id=session_id
                )
                if existing is not None:
                    return session_id
            except Exception:
                logger.warning(
                    "No se pudo verificar la sesión ADK %s; se creará una nueva", session_id
                )
        session = await runner.session_service.create_session(app_name=APP_NAME, user_id=user_id)
        if history:
            await self._seed_history(session, history)
        return session.id

    async def _seed_history(self, session: Any, history: list[tuple[str, str]]) -> None:
        """Inyecta turnos previos en una sesión nueva como eventos user/model.

        Reconstruye el contexto del LLM desde la BD: cada mensaje de usuario va
        como `role="user"` y cada respuesta del agente como `role="model"`.
        """
        from google.adk.events import Event
        from google.genai import types

        runner = self._get_runner()
        agent_name = runner.agent.name
        for role, content in history:
            if not content:
                continue
            if role == "user":
                event = Event(
                    author="user",
                    content=types.Content(role="user", parts=[types.Part(text=content)]),
                )
            else:
                event = Event(
                    author=agent_name,
                    content=types.Content(role="model", parts=[types.Part(text=content)]),
                )
            await runner.session_service.append_event(session, event)

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
            ficha_urls: list[str] = []
            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content
            ):
                text = _event_text(event)
                if text:
                    reply = text
                ficha_urls.extend(_ficha_urls_from_event(event))
            reply = reply or "El agente no devolvió respuesta. Intenta reformular tu consulta."
            return _ensure_ficha_urls(reply, ficha_urls)
        except Exception:
            logger.exception("Error al consultar al agente (Vertex AI)")
            return (
                "Lo siento, hubo un problema al contactar al Agente IA. "
                "Intenta nuevamente en unos momentos."
            )


# Factory / provider (creacional): función de acceso usada como dependencia
# (FastAPI Depends). Devuelve el singleton y permite sobrescribirlo en tests.
def get_ulima_agent() -> UlimaAgentClient:
    return _agent_client


# Singleton (creacional): una única instancia por proceso, expuesta vía
# get_ulima_agent(). El InMemoryRunner de ADK de adentro se crea perezosamente.
_agent_client = UlimaAgentClient()
