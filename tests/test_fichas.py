"""Tests de las fichas visuales (one page) del agente y su ruta de servido.

Las tools consultan la BD vía `ulima_agent.tools.fichas.fetch_all`; aquí se
monkeypatchea con datos de prueba (no se toca Neon). La ruta se prueba contra la
app ASGI reusando la caché de módulo compartida (el agente corre in-process).
"""

import time

from httpx import AsyncClient
from ulima_agent.tools import fichas

from app.integrations.agent import ulima_agent as agent_client

# --- fakes de fetch_all (enrutan por la forma del SQL) ---

async def _fake_curso(sql: str, params=None):
    s = " ".join(sql.split())
    if "jsonb_array_elements_text(prerequisites)" in s:  # cursos que habilita
        return [{"codigo": "650061", "nombre": "Estructuras de Datos II"}]
    if "FROM reviews r" in s and "AVG" in s:  # reputación del profe
        return [{"rating_promedio": 4.3, "num_resenas": 12}]
    if "FROM courses c" in s:  # detalle del curso
        return [{
            "codigo": "650059", "nombre": "Estructuras de Datos I", "nivel": "5",
            "creditos": 4, "difficulty": 4, "tipo": "obligatorio",
            "prerrequisitos": ["Programación Orientada a Objetos"],
            "professor_id": "pid-1", "profesor": "Hernán Quintana",
        }]
    return []


async def _fake_profe(sql: str, params=None):
    s = " ".join(sql.split())
    if "FROM professors p" in s:  # perfil + reputación (se chequea primero)
        return [{
            "id": "pid-1", "nombre": "Hernán Quintana", "departamento": "Ing. Sistemas",
            "grado": "Bachiller", "biografia": "Docente de software", "correo": "h@ulima.edu.pe",
            "disponibilidad": "Lun 10-12", "photo_path": None,
            "num_resenas": 3, "rating_promedio": 4.3,
        }]
    if "FROM reviews r" in s:  # reseñas
        return [{"rating": 5, "comentario": "Explica con ejemplos <reales> & claros"}]
    if "FROM courses" in s and "professor_id" in s:  # cursos que dicta
        return [{"codigo": "650022", "nombre": "Programación Web", "nivel": "6", "difficulty": 3}]
    return []


# --- tools ---

async def test_generar_ficha_curso_ok(monkeypatch):
    monkeypatch.setattr(fichas, "fetch_all", _fake_curso)
    res = await fichas.generar_ficha_curso("650059")

    assert res["encontrado"] is True
    assert res["tipo"] == "curso"
    assert "/api/v1/fichas/" in res["url"]

    ficha_id = res["url"].rsplit("/", 1)[-1]
    doc = fichas.read_ficha_html(ficha_id)
    assert doc is not None
    assert "Estructuras de Datos I" in doc          # cabecera del curso
    assert "Estructuras de Datos II" in doc         # curso que habilita
    assert "Consultas SQL usadas" in doc            # panel de transparencia
    assert "jsonb_array_elements_text(prerequisites)" in doc  # el SQL aparece en el panel


async def test_generar_ficha_curso_no_encontrado(monkeypatch):
    async def _vacio(sql, params=None):
        return []

    monkeypatch.setattr(fichas, "fetch_all", _vacio)
    res = await fichas.generar_ficha_curso("no-existe")
    assert res["encontrado"] is False
    assert "url" not in res


async def test_generar_ficha_profesor_escapa_comentarios(monkeypatch):
    monkeypatch.setattr(fichas, "fetch_all", _fake_profe)
    res = await fichas.generar_ficha_profesor("Quintana")

    assert res["encontrado"] is True
    ficha_id = res["url"].rsplit("/", 1)[-1]
    doc = fichas.read_ficha_html(ficha_id)
    assert "Hernán Quintana" in doc
    assert "Programación Web" in doc                # curso que dicta (chip)
    assert "&lt;reales&gt; &amp; claros" in doc     # comentario escapado
    assert "<reales>" not in doc                    # no hay HTML crudo del usuario
    # Sin foto -> monograma de iniciales (no <img>).
    assert "class='mono'" in doc
    assert "/api/v1/professors/pid-1/photo" not in doc


async def test_generar_ficha_profesor_con_foto(monkeypatch):
    async def _fake(sql: str, params=None):
        s = " ".join(sql.split())
        if "FROM professors p" in s:
            return [{
                "id": "pid-9", "nombre": "Ana Torres", "departamento": "Ing. Sistemas",
                "grado": "Doctora", "biografia": "IA aplicada", "correo": "a@ulima.edu.pe",
                "disponibilidad": "Mar 14-16",
                "photo_path": "gs://bucket/professors/pid-9.png",
                "num_resenas": 2, "rating_promedio": 5.0,
            }]
        return []

    monkeypatch.setattr(fichas, "fetch_all", _fake)
    res = await fichas.generar_ficha_profesor("Ana")
    doc = fichas.read_ficha_html(res["url"].rsplit("/", 1)[-1])
    # Con foto -> <img> a la ruta pública (no monograma).
    assert "/api/v1/professors/pid-9/photo" in doc
    assert "<img class='avatar'" in doc
    assert "class='mono'" not in doc


async def test_ficha_profesor_busca_por_palabras_sin_orden(monkeypatch):
    """'edwin escobedo' debe encontrar 'Escobedo Cardenas Edwin Jonathan': cada palabra
    se busca por separado (AND), sin exigir la frase contigua ni el orden."""
    captura: dict = {}

    async def _fake(sql: str, params=None):
        s = " ".join(sql.split())
        if "FROM professors p" in s:
            captura["sql"] = s
            captura["params"] = dict(params or {})
            return [{
                "id": "pid-1", "nombre": "Escobedo Cardenas Edwin Jonathan",
                "departamento": "Ing. Sistemas", "grado": "Magíster", "biografia": "TI",
                "correo": "e@ulima.edu.pe", "disponibilidad": None, "photo_path": None,
                "num_resenas": 2, "rating_promedio": 5.0,
            }]
        return []

    monkeypatch.setattr(fichas, "fetch_all", _fake)
    res = await fichas.generar_ficha_profesor("edwin escobedo")

    assert res["encontrado"] is True
    # Dos palabras -> dos condiciones (tok0, tok1) combinadas con AND, no un solo LIKE.
    assert captura["params"].get("tok0") == "%edwin%"
    assert captura["params"].get("tok1") == "%escobedo%"
    assert " AND " in captura["sql"]
    assert "%edwin escobedo%" not in captura["params"].values()


async def test_ruta_foto_profesor_200_y_404(client: AsyncClient, monkeypatch):
    from fastapi import HTTPException

    from app.domains.admin import service as admin_service

    async def _fake_get_photo(db, professor_id: str):
        if professor_id == "pid-9":
            return b"\x89PNG\r\n\x1a\n", "image/png"
        raise HTTPException(status_code=404, detail="Este profesor no tiene foto cargada.")

    monkeypatch.setattr(admin_service, "get_professor_photo", _fake_get_photo)

    ok = await client.get("/api/v1/professors/pid-9/photo")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("image/")

    faltante = await client.get("/api/v1/professors/pid-0/photo")
    assert faltante.status_code == 404


# --- ruta GET /api/v1/fichas/{id} ---

async def test_ruta_ficha_200_y_404(client: AsyncClient):
    ficha_id = fichas._store_ficha("<html><body>hola ficha</body></html>")

    ok = await client.get(f"/api/v1/fichas/{ficha_id}")
    assert ok.status_code == 200
    assert "hola ficha" in ok.text
    assert ok.headers["content-type"].startswith("text/html")

    faltante = await client.get("/api/v1/fichas/inexistente")
    assert faltante.status_code == 404


async def test_ficha_expira(client: AsyncClient):
    ficha_id = fichas._store_ficha("<html>vieja</html>")
    _, doc = fichas.FICHA_HTML_CACHE[ficha_id]
    # Fuerza un timestamp más viejo que el TTL.
    fichas.FICHA_HTML_CACHE[ficha_id] = (time.time() - fichas.FICHA_TTL_SECONDS - 10, doc)

    assert fichas.read_ficha_html(ficha_id) is None
    expirada = await client.get(f"/api/v1/fichas/{ficha_id}")
    assert expirada.status_code == 404


# --- inyección de la URL de la ficha en el texto de la respuesta del agente ---

class _FakeFR:
    def __init__(self, name: str, response: dict):
        self.name = name
        self.response = response


class _FakeEvent:
    def __init__(self, frs: list):
        self._frs = frs

    def get_function_responses(self):
        return self._frs


def test_ensure_ficha_urls_agrega_si_falta():
    reply = "Preparé la ficha del curso."
    out = agent_client._ensure_ficha_urls(reply, ["/api/v1/fichas/abc"])
    assert out.startswith(reply)
    assert "/api/v1/fichas/abc" in out


def test_ensure_ficha_urls_no_duplica():
    reply = "Puedes verla aquí: /api/v1/fichas/abc"
    out = agent_client._ensure_ficha_urls(reply, ["/api/v1/fichas/abc"])
    assert out.count("/api/v1/fichas/abc") == 1


def test_ficha_urls_from_event_filtra_por_tool():
    ev = _FakeEvent([
        _FakeFR("generar_ficha_curso", {"encontrado": True, "url": "/api/v1/fichas/abc"}),
        _FakeFR("buscar_profesor", {"encontrado": True}),  # no es tool de ficha -> ignorado
        _FakeFR("generar_ficha_profesor", {"encontrado": False}),  # sin url -> ignorado
    ])
    assert agent_client._ficha_urls_from_event(ev) == ["/api/v1/fichas/abc"]
