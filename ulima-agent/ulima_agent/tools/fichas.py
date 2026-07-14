"""Fichas visuales ("one page") de curso y profesor para el agente SmartSched.

Inspirado en el `generate_one_page` de FerVentas: la herramienta corre varias
consultas SQL de solo lectura contra la BD (Neon), arma un payload y renderiza
una PÁGINA HTML autocontenida (self-contained, sin recursos externos) que el
estudiante abre en el navegador. La herramienta NO devuelve el HTML al modelo
(sería enorme): lo guarda en una caché de módulo y devuelve solo una URL.

Entrega (fase actual): el agente corre in-process dentro del backend, así que la
ruta `GET /api/v1/fichas/{id}` (dominio `app/domains/fichas/`) lee esta misma
caché del proceso y sirve el HTML. La URL es opaca (uuid) y pública: los datos
provienen de la malla, y así un iframe o una pestaña nueva no necesita mandar
`Authorization`.

Transparencia: cada ficha incluye un panel colapsable "Consultas SQL usadas" con
el SQL y los parámetros que la generaron (de ahí que el one page "tenga las
queries"). Todo texto dinámico se escapa con `html.escape` para evitar inyección.
"""

import html
import logging
import os
import re
import time
import uuid

from ..db import fetch_all

# Mismo emparejamiento de nombres que las tools de texto (buscar_profesor/detalle_curso):
# exige TODAS las palabras, sin importar el orden ni los acentos. Así "edwin escobedo"
# encuentra a "Escobedo Cardenas Edwin Jonathan" (antes un solo ILIKE '%edwin escobedo%'
# fallaba porque pedía la frase contigua y en ese orden).
from .academic import _name_where

logger = logging.getLogger(__name__)

_ERROR_MSG = "No se pudo generar la ficha en este momento."

# Etiquetas de la escala de dificultad (courses.difficulty, 1..5).
_DIFICULTAD = {1: "muy baja", 2: "baja", 3: "media", 4: "alta", 5: "muy alta"}

# --- Caché de HTML a nivel de módulo (id -> (timestamp, html)) ---
# La comparte la ruta del backend porque el agente corre in-process.
FICHA_HTML_CACHE: dict[str, tuple[float, str]] = {}
FICHA_TTL_SECONDS = 3600  # 1 hora
FICHA_MAX_ENTRIES = 200


def _evict() -> None:
    """Elimina fichas expiradas y limita el tamaño (elimina las más antiguas)."""
    ahora = time.time()
    expiradas = [k for k, (ts, _) in FICHA_HTML_CACHE.items() if ahora - ts > FICHA_TTL_SECONDS]
    for k in expiradas:
        FICHA_HTML_CACHE.pop(k, None)
    while len(FICHA_HTML_CACHE) > FICHA_MAX_ENTRIES:
        # dict conserva el orden de inserción: el primero es el más antiguo.
        FICHA_HTML_CACHE.pop(next(iter(FICHA_HTML_CACHE)), None)


def _store_ficha(doc: str) -> str:
    """Guarda el HTML y devuelve su id opaco."""
    ficha_id = uuid.uuid4().hex
    FICHA_HTML_CACHE[ficha_id] = (time.time(), doc)
    _evict()
    return ficha_id


def read_ficha_html(ficha_id: str) -> str | None:
    """Devuelve el HTML de una ficha, o None si no existe o expiró.

    La usa la ruta `GET /api/v1/fichas/{id}` del backend.
    """
    entry = FICHA_HTML_CACHE.get(ficha_id)
    if entry is None:
        return None
    ts, doc = entry
    if time.time() - ts > FICHA_TTL_SECONDS:
        FICHA_HTML_CACHE.pop(ficha_id, None)
        return None
    return doc


def _build_url(path: str) -> str:
    """Antepone `AGENT_PUBLIC_BASE_URL` a *path* si está definido; si no, lo deja relativo.

    En dev conviene exportar AGENT_PUBLIC_BASE_URL=http://localhost:8000 para que el
    enlace sea directamente navegable; en prod, la URL pública del backend. Las rutas
    relativas también funcionan dentro del iframe de la ficha, porque el documento lo
    sirve el propio backend (misma raíz).
    """
    base = (os.getenv("AGENT_PUBLIC_BASE_URL") or "").rstrip("/")
    return f"{base}{path}" if base else path


def _build_ficha_url(ficha_id: str) -> str:
    """URL a la ficha (absoluta o relativa, según `AGENT_PUBLIC_BASE_URL`)."""
    return _build_url(f"/api/v1/fichas/{ficha_id}")


# =========================================================================
# RENDER HTML
# =========================================================================

_CSS = """
:root { --naranja:#f97316; --tinta:#2b2b2b; --gris:#8a8a8a; --linea:#ececec;
  --crema:#faf6f0; --label:#c08457; --chip:#f3ede4; --fondo:#f4f4f5; }
* { box-sizing:border-box; }
body { margin:0; background:var(--fondo); color:var(--tinta);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.55; padding:20px; }
.wrap { max-width:820px; margin:0 auto; }
.serif { font-family:Georgia,"Times New Roman",serif; }
.card { background:#fff; border:1px solid var(--linea); border-top:5px solid var(--naranja);
  border-radius:16px; overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,.06); margin-bottom:16px; }
.grid { display:grid; grid-template-columns:minmax(0,0.92fr) minmax(0,1.08fr); }
.col-left { background:var(--crema); padding:28px 26px; }
.col-right { padding:28px 26px; border-left:1px solid var(--linea); }
@media (max-width:560px) {
  .grid { grid-template-columns:1fr; }
  .col-right { border-left:0; border-top:1px solid var(--linea); }
}
.avatar, .mono { width:104px; height:104px; border-radius:50%; }
.avatar { object-fit:cover; border:1px solid rgba(0,0,0,.08); display:block; }
.mono { display:flex; align-items:center; justify-content:center; background:var(--naranja);
  color:#fff; font-size:2rem; font-weight:600; font-family:Georgia,serif; }
h1 { font-size:1.7rem; line-height:1.15; margin:18px 0 6px; font-weight:600; }
.sub { color:var(--gris); font-size:.9rem; margin:0; }
.label { font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; color:var(--label);
  font-weight:600; margin:0 0 8px; }
.rating-box { background:rgba(249,115,22,.07); border-radius:12px; padding:12px 14px;
  margin:18px 0 0; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.stars { color:var(--naranja); font-size:1.05rem; letter-spacing:2px; }
.rating-num { font-weight:700; font-size:1.2rem; }
.rating-meta { color:var(--gris); font-size:.85rem; }
.contacto { margin-top:22px; }
.contacto a { color:var(--naranja); text-decoration:none; word-break:break-word; }
.contacto p { margin:4px 0; font-size:.9rem; }
.block { margin-bottom:22px; }
.block:last-child { margin-bottom:0; }
.desc { margin:0; font-size:.95rem; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }
.chip { background:var(--chip); border:1px solid var(--linea); border-radius:999px;
  padding:5px 12px; font-size:.8rem; color:var(--tinta); }
.quotes { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }
@media (max-width:460px) { .quotes { grid-template-columns:1fr; } }
.quote { border-left:3px solid var(--naranja); background:#fcfaf7; border-radius:0 10px 10px 0;
  padding:10px 14px; font-family:Georgia,serif; font-style:italic; color:#4a4a4a; font-size:.9rem; }
.quote .qstars { display:block; font-style:normal; color:var(--naranja); font-size:.72rem;
  letter-spacing:1px; margin-top:6px; }
.row-between { display:flex; align-items:baseline; justify-content:space-between; gap:8px;
  flex-wrap:wrap; }
.note { font-style:italic; color:var(--gris); font-size:.75rem; }
.muted { color:var(--gris); font-style:italic; }
.head-band { padding:26px 28px; }
.badges { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
.badge { background:var(--chip); border:1px solid var(--linea); border-radius:999px;
  padding:5px 12px; font-size:.8rem; color:var(--tinta); }
.badge b { color:var(--naranja); }
.dif { display:flex; gap:6px; margin:10px 0 0; }
.dif span { flex:1; height:10px; border-radius:5px; background:#e7e2da; }
.dif span.on { background:var(--naranja); }
.dif-txt { font-size:.85rem; color:var(--gris); margin:6px 0 0; }
ul { margin:8px 0 0; padding-left:18px; }
li { margin:3px 0; font-size:.92rem; }
.sqlcard { background:#fff; border:1px solid var(--linea); border-radius:14px;
  padding:18px 20px; margin-bottom:16px; }
.sqlcard h2 { font-size:.72rem; text-transform:uppercase; letter-spacing:.12em;
  color:var(--label); font-weight:600; margin:0 0 4px; }
details { margin-top:8px; }
summary { cursor:pointer; font-weight:600; color:var(--tinta); font-size:.85rem; }
pre { background:#faf7f2; border:1px solid var(--linea); border-radius:8px; padding:12px;
  overflow-x:auto; font-size:.76rem; margin:8px 0; white-space:pre-wrap; word-break:break-word; }
.foot { text-align:center; color:var(--gris); font-size:.72rem; margin-top:6px; }
"""


def _e(value: object) -> str:
    """Escapa a HTML de forma segura (None -> cadena vacía)."""
    return html.escape("" if value is None else str(value))


def _page(titulo: str, cuerpo: str) -> str:
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_e(titulo)}</title><style>{_CSS}</style></head>"
        f"<body><div class='wrap'>{cuerpo}"
        "<p class='foot'>SmartSched · Universidad de Lima — ficha generada por el asistente académico</p>"
        "</div></body></html>"
    )


def _barra_dificultad(dif: int | None) -> str:
    if not dif:
        return "<p class='dif-txt muted'>Dificultad no registrada.</p>"
    segmentos = "".join(f"<span class='{'on' if i <= dif else ''}'></span>" for i in range(1, 6))
    etiqueta = _DIFICULTAD.get(dif, "—")
    return (
        f"<div class='dif'>{segmentos}</div>"
        f"<p class='dif-txt'>Dificultad estimada: <b>{dif}/5</b> ({_e(etiqueta)}). "
        "Es orientativa, no oficial: depende del profesor, la sección y tu base previa.</p>"
    )


def _fmt_rating(rating: object) -> str:
    """Formatea el rating a una decimal ('5.0', '4.3')."""
    try:
        return f"{float(rating):.1f}"  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _e(rating)


def _estrellas_str(rating: float) -> str:
    llenas = max(0, min(5, round(rating)))
    return f"{'★' * llenas}{'☆' * (5 - llenas)}"


def _rating_box(rating: float | None, num_resenas: object) -> str:
    """Caja de reputación (estrellas + promedio + nº de reseñas)."""
    if rating is None:
        return "<div class='rating-box'><span class='muted'>Sin reseñas registradas</span></div>"
    return (
        f"<div class='rating-box'>"
        f"<span class='stars'>{_estrellas_str(float(rating))}</span>"
        f"<span class='rating-num'>{_fmt_rating(rating)}</span>"
        f"<span class='rating-meta'>· {_e(num_resenas or 0)} reseña(s)</span></div>"
    )


def _iniciales(nombre: str | None) -> str:
    """Iniciales del profesor para el monograma (sin el título Dr./Mg./Ing.)."""
    limpio = re.sub(r"(?i)^(?:dr\.?|dra\.?|mg\.?|ing\.?|lic\.?|prof\.?)\s*", "", nombre or "").strip()
    partes = limpio.split()
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()


def _quote_card(resena: dict) -> str:
    """Tarjeta de cita para la sección 'Voz de estudiantes'."""
    texto = resena.get("comentario") or "(sin comentario)"
    rating = resena.get("rating")
    estrellas = ""
    if rating is not None:
        try:
            estrellas = f"<span class='qstars'>{_estrellas_str(float(rating))}</span>"
        except (TypeError, ValueError):
            estrellas = ""
    return f"<div class='quote'>“{_e(texto)}”{estrellas}</div>"


def _panel_sql(consultas: list[dict]) -> str:
    if not consultas:
        return ""
    filas = []
    for c in consultas:
        params = c.get("params") or {}
        params_txt = "\n".join(f"  {k} = {v!r}" for k, v in params.items()) or "  (sin parámetros)"
        filas.append(
            f"<details><summary>{_e(c['titulo'])}</summary>"
            f"<pre>{_e(c['sql'].strip())}\n\n-- parámetros:\n{_e(params_txt)}</pre></details>"
        )
    return (
        "<div class='sqlcard'><h2>Consultas SQL usadas</h2>"
        "<p class='dif-txt'>Estas son las consultas de solo lectura que generaron esta ficha.</p>"
        + "".join(filas)
        + "</div>"
    )


def _render_ficha_curso(curso: dict, habilita: list[dict], profe: dict | None,
                        consultas: list[dict]) -> str:
    nombre = curso.get("nombre") or "Curso"
    tipo = (curso.get("tipo") or "").capitalize()
    badges = (
        f"<span class='badge'>Nivel <b>{_e(curso.get('nivel'))}</b></span>"
        f"<span class='badge'>Créditos <b>{_e(curso.get('creditos'))}</b></span>"
        + (f"<span class='badge'>{_e(tipo)}</span>" if tipo else "")
    )
    prereqs = list(curso.get("prerrequisitos") or [])
    prereqs_html = (
        "<ul>" + "".join(f"<li>{_e(p)}</li>" for p in prereqs) + "</ul>"
        if prereqs else "<p class='muted'>No tiene prerrequisitos.</p>"
    )
    habilita_html = (
        "<ul>" + "".join(f"<li>{_e(h.get('codigo'))} — {_e(h.get('nombre'))}</li>" for h in habilita)
        + "</ul>" if habilita else "<p class='muted'>No es prerrequisito directo de otros cursos.</p>"
    )
    if profe:
        profe_html = (
            f"<p class='desc'><b>{_e(profe.get('nombre'))}</b></p>"
            f"{_rating_box(profe.get('rating_promedio'), profe.get('num_resenas'))}"
        )
    else:
        profe_html = (
            "<p class='muted'>No hay un profesor asignado a este curso en la base de datos.</p>"
        )

    cuerpo = (
        "<div class='card'>"
        f"<div class='head-band'><h1 class='serif'>{_e(nombre)}</h1>"
        f"<p class='sub'>Código {_e(curso.get('codigo'))}</p>"
        f"<div class='badges'>{badges}</div></div>"
        "<div class='grid'>"
        "<section class='col-left' style='background:#fff'>"
        f"<div class='block'><p class='label'>Dificultad</p>{_barra_dificultad(curso.get('difficulty'))}</div>"
        f"<div class='block'><p class='label'>Prerrequisitos</p>{prereqs_html}</div>"
        "</section>"
        "<section class='col-right'>"
        f"<div class='block'><p class='label'>Habilita estos cursos</p>{habilita_html}</div>"
        f"<div class='block'><p class='label'>Profesor asignado</p>{profe_html}</div>"
        "</section>"
        "</div></div>"
        f"{_panel_sql(consultas)}"
    )
    return _page(f"Ficha del curso — {nombre}", cuerpo)


def _render_ficha_profesor(profe: dict, resenas: list[dict], cursos: list[dict],
                           consultas: list[dict]) -> str:
    nombre = profe.get("nombre") or "Profesor"
    pid = profe.get("id")
    photo_path = profe.get("photo_path")
    if photo_path and pid:
        foto_url = _build_url(f"/api/v1/professors/{pid}/photo")
        avatar = f"<img class='avatar' src='{_e(foto_url)}' alt='Foto de {_e(nombre)}'>"
    else:
        avatar = f"<div class='mono'>{_e(_iniciales(nombre))}</div>"

    sub_parts = [p for p in (profe.get("departamento"), profe.get("grado")) if p]
    sub = _e(" · ".join(sub_parts)) if sub_parts else "<span class='muted'>Docente registrado</span>"

    disp = profe.get("disponibilidad")
    disp_html = _e(disp) if disp else "<span class='muted'>no registrado</span>"
    correo = profe.get("correo")
    correo_html = (
        f"<a href='mailto:{_e(correo)}'>{_e(correo)}</a>"
        if correo else "<span class='muted'>no registrado</span>"
    )

    bio = profe.get("biografia")
    bio_html = _e(bio) if bio else "<span class='muted'>Sin biografía registrada.</span>"

    if cursos:
        chips = "".join(f"<span class='chip'>{_e(c.get('nombre'))}</span>" for c in cursos)
        chips_block = (
            "<div class='block'><p class='label'>Cursos que dicta</p>"
            f"<div class='chips'>{chips}</div></div>"
        )
    else:
        chips_block = (
            "<div class='block'><p class='label'>Cursos que dicta</p>"
            "<p class='muted'>No hay cursos asignados en la base de datos.</p></div>"
        )

    if resenas:
        voz = f"<div class='quotes'>{''.join(_quote_card(r) for r in resenas)}</div>"
    else:
        voz = "<p class='muted'>Aún no hay reseñas registradas para este profesor.</p>"

    cuerpo = (
        "<div class='card'><div class='grid'>"
        "<aside class='col-left'>"
        f"{avatar}"
        f"<h1 class='serif'>{_e(nombre)}</h1>"
        f"<p class='sub'>{sub}</p>"
        f"{_rating_box(profe.get('rating_promedio'), profe.get('num_resenas'))}"
        "<div class='contacto'><p class='label'>Contacto</p>"
        f"<p>{correo_html}</p>"
        f"<p class='rating-meta'>Horario de atención: {disp_html}</p></div>"
        "</aside>"
        "<section class='col-right'>"
        f"<div class='block'><p class='label'>Especialidad</p><p class='desc'>{bio_html}</p></div>"
        f"{chips_block}"
        "<div class='block'>"
        "<div class='row-between'><p class='label' style='margin:0'>Voz de estudiantes</p>"
        "<span class='note'>Percepciones, no un dato oficial</span></div>"
        f"{voz}</div>"
        "</section>"
        "</div></div>"
        f"{_panel_sql(consultas)}"
    )
    return _page(f"Ficha del profesor — {nombre}", cuerpo)


# =========================================================================
# TOOLS
# =========================================================================

def _sql_curso(where_nombre: str) -> str:
    """SELECT del detalle del curso: coincide por código exacto O por nombre (todas
    las palabras, sin orden ni acentos; `where_nombre` lo arma `_name_where`)."""
    return f"""
SELECT c.code AS codigo, c.name AS nombre, c.level AS nivel, c.credits AS creditos,
       c.difficulty AS difficulty, c.course_type AS tipo, c.prerequisites AS prerrequisitos,
       c.professor_id AS professor_id, p.name AS profesor
FROM courses c
LEFT JOIN professors p ON p.id = c.professor_id
WHERE lower(c.code) = lower(:q) OR ({where_nombre})
ORDER BY (lower(c.code) = lower(:q)) DESC, c.name
LIMIT 1
"""

_SQL_HABILITA = """
SELECT code AS codigo, name AS nombre
FROM courses
WHERE jsonb_typeof(prerequisites) = 'array'
  AND EXISTS (
    SELECT 1 FROM jsonb_array_elements_text(prerequisites) AS pr WHERE pr ILIKE :nombre
  )
ORDER BY CASE WHEN level ~ '^[0-9]+$' THEN level::int ELSE 99 END, code
LIMIT 50
"""

_SQL_REPUTACION = """
SELECT ROUND(AVG(r.rating)::numeric, 2) AS rating_promedio, COUNT(r.id) AS num_resenas
FROM reviews r
WHERE r.professor_id = :pid
"""


async def generar_ficha_curso(curso: str) -> dict:
    """Genera una FICHA VISUAL (página web) de un curso y devuelve su URL.

    La ficha reúne, con consultas SQL a la base de datos, el detalle del curso
    (nivel, créditos, dificultad 1-5, tipo), sus prerrequisitos, qué cursos habilita
    y el profesor asignado con su reputación. Úsala cuando el estudiante pida una
    "ficha", un "resumen", una "página" o un "one page" de un curso, o cuando un
    resumen visual ayude más que texto. Comparte la "url" que devuelve en tu
    respuesta, en texto plano.

    Args:
        curso: Código exacto (p. ej. "650059") o nombre/parte del nombre del curso.

    Returns:
        dict con "encontrado" (bool); si es true, "url", "titulo" y "tipo".
    """
    curso = (curso or "").strip()
    if not curso:
        return {"encontrado": False, "mensaje": "Indica el código o nombre del curso."}
    consultas: list[dict] = []
    try:
        where_nombre, p_nombre = _name_where("c.name", curso)
        sql_curso = _sql_curso(where_nombre)
        p_curso = {"q": curso, **p_nombre}
        consultas.append({"titulo": "Detalle del curso", "sql": sql_curso, "params": p_curso})
        filas = await fetch_all(sql_curso, p_curso)
        if not filas:
            return {
                "encontrado": False,
                "mensaje": f"No se encontró un curso con código o nombre '{curso}'.",
            }
        datos = filas[0]
        nombre = datos["nombre"]

        p_hab = {"nombre": nombre}
        consultas.append({"titulo": "Cursos que habilita", "sql": _SQL_HABILITA, "params": p_hab})
        habilita = await fetch_all(_SQL_HABILITA, p_hab)

        profe: dict | None = None
        if datos.get("professor_id"):
            p_rep = {"pid": datos["professor_id"]}
            consultas.append({"titulo": "Reputación del profesor", "sql": _SQL_REPUTACION, "params": p_rep})
            rep = await fetch_all(_SQL_REPUTACION, p_rep)
            profe = {"nombre": datos.get("profesor"), **(rep[0] if rep else {})}

        doc = _render_ficha_curso(datos, habilita, profe, consultas)
    except Exception:
        logger.exception("generar_ficha_curso falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    ficha_id = _store_ficha(doc)
    return {
        "encontrado": True,
        "tipo": "curso",
        "titulo": f"{datos.get('codigo')} — {nombre}",
        "url": _build_ficha_url(ficha_id),
    }


def _sql_profesor(where_nombre: str) -> str:
    """SELECT del perfil + reputación del profesor, filtrando por nombre con todas
    las palabras, sin orden ni acentos (`where_nombre` lo arma `_name_where`)."""
    return f"""
SELECT p.id AS id, p.name AS nombre, p.department AS departamento, p.degree AS grado,
       p.bio AS biografia, p.email AS correo, p.availability AS disponibilidad,
       p.photo_gcs_path AS photo_path,
       COUNT(r.id) AS num_resenas, ROUND(AVG(r.rating)::numeric, 2) AS rating_promedio
FROM professors p
LEFT JOIN reviews r ON r.professor_id = p.id
WHERE {where_nombre}
GROUP BY p.id, p.name, p.department, p.degree, p.bio, p.email, p.availability, p.photo_gcs_path
ORDER BY p.name
LIMIT 1
"""

_SQL_RESENAS = """
SELECT r.rating, r.comment AS comentario
FROM reviews r
WHERE r.professor_id = :pid
ORDER BY r.created_at DESC
LIMIT 50
"""

_SQL_CURSOS_PROFE = """
SELECT code AS codigo, name AS nombre, level AS nivel, difficulty
FROM courses
WHERE professor_id = :pid
ORDER BY code
"""


async def generar_ficha_profesor(nombre: str) -> dict:
    """Genera una FICHA VISUAL (página web) de un profesor y devuelve su URL.

    La ficha reúne, con consultas SQL, el perfil del profesor (departamento, grado,
    biografía, correo, horario de atención), su reputación (rating promedio y número
    de reseñas), las reseñas de estudiantes y los cursos que dicta. Úsala cuando el
    estudiante pida una "ficha", un "resumen" o una "página" de un profesor. Comparte
    la "url" que devuelve en tu respuesta, en texto plano.

    Args:
        nombre: Nombre completo o parcial del profesor.

    Returns:
        dict con "encontrado" (bool); si es true, "url", "titulo" y "tipo".
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return {"encontrado": False, "mensaje": "Indica el nombre del profesor."}
    consultas: list[dict] = []
    try:
        where_nombre, p_prof = _name_where("p.name", nombre)
        sql_prof = _sql_profesor(where_nombre)
        consultas.append({"titulo": "Perfil y reputación", "sql": sql_prof, "params": p_prof})
        filas = await fetch_all(sql_prof, p_prof)
        if not filas:
            return {
                "encontrado": False,
                "mensaje": f"No se encontró ningún profesor que coincida con '{nombre}'.",
            }
        datos = filas[0]
        pid = datos.get("id")

        p_pid = {"pid": pid}
        consultas.append({"titulo": "Reseñas de estudiantes", "sql": _SQL_RESENAS, "params": p_pid})
        resenas = await fetch_all(_SQL_RESENAS, p_pid)
        consultas.append({"titulo": "Cursos que dicta", "sql": _SQL_CURSOS_PROFE, "params": p_pid})
        cursos = await fetch_all(_SQL_CURSOS_PROFE, p_pid)

        doc = _render_ficha_profesor(datos, resenas, cursos, consultas)
    except Exception:
        logger.exception("generar_ficha_profesor falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    ficha_id = _store_ficha(doc)
    return {
        "encontrado": True,
        "tipo": "profesor",
        "titulo": f"Ficha de {datos.get('nombre')}",
        "url": _build_ficha_url(ficha_id),
    }
