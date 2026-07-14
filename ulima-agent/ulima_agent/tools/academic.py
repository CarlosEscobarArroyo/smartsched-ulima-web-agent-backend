"""Herramientas (tools) del agente para consultar la BD académica de SmartSched.

Son funciones tipadas y de propósito fijo (no NL->SQL): cada una encapsula un
SELECT parametrizado de solo lectura contra Neon. El LLM las invoca para responder
consultas de profesores y cursos (US-15/16/17/18) con datos reales, en vez de
depender de información incrustada en el prompt.

Todas devuelven un dict serializable a JSON y degradan con elegancia: ante un
error de conexión devuelven {"error": ...} para que el agente pueda avisar en
lugar de fallar; ante 0 resultados devuelven "encontrado": false con un mensaje.
"""

import logging

from ..db import fetch_all

logger = logging.getLogger(__name__)

_ERROR_MSG = "No se pudo consultar la base de datos en este momento."

# Coincidencia de nombres INSENSIBLE A ACENTOS: en la BD los nombres suelen ir
# sin tildes ("Gutierrez Cardenas", "Calculo III"), pero el usuario/LLM escribe
# con tildes ("Gutiérrez", "Cálculo"). Se normalizan ambos lados con translate
# (no requiere la extensión unaccent en Neon). ñ->n y ü->u para robustez.
_ACENTOS = "áéíóúüñ"
_SIN_ACENTOS = "aeiouun"


def _norm(expr: str) -> str:
    """Expresión SQL que baja a minúsculas y quita acentos de `expr`."""
    return f"translate(lower({expr}), '{_ACENTOS}', '{_SIN_ACENTOS}')"


def _name_where(column: str, nombre: str) -> tuple[str, dict[str, str]]:
    """WHERE que exige TODAS las palabras del nombre, sin importar el orden ni acentos.

    En la BD los nombres van "Apellido1 Apellido2 Nombre1 Nombre2" (p. ej.
    "Escobedo Cardenas Edwin Jonathan"), pero el usuario suele escribir en otro
    orden ("Edwin Escobedo"). Un solo LIKE '%edwin escobedo%' fallaría porque exige
    las palabras contiguas y en ese orden. Aquí cada palabra se busca como subcadena
    y se combinan con AND, así el orden da igual y basta con que aparezcan todas.
    """
    tokens = [t for t in nombre.split() if t]
    if not tokens:
        return "TRUE", {}
    conds: list[str] = []
    params: dict[str, str] = {}
    for i, tok in enumerate(tokens):
        key = f"tok{i}"
        conds.append(f"{_norm(column)} LIKE {_norm(':' + key)}")
        params[key] = f"%{tok}%"
    return " AND ".join(conds), params


# Etiquetas de la escala de dificultad (columna courses.difficulty, 1..5).
_DIFICULTAD = {1: "muy baja", 2: "baja", 3: "media", 4: "alta", 5: "muy alta"}


def _con_etiqueta_dificultad(curso: dict) -> dict:
    """Agrega 'dificultad_texto' a partir del número (si existe)."""
    dif = curso.get("difficulty")
    curso["dificultad_texto"] = _DIFICULTAD.get(dif) if dif is not None else None
    return curso


async def buscar_profesor(nombre: str) -> dict:
    """Busca profesores por nombre (o parte del nombre) y devuelve su ficha.

    Incluye departamento, grado académico, biografía, correo, horario de atención
    (availability) y su reputación: rating promedio (escala 1 a 5) y número de
    reseñas de estudiantes. Úsala para consultas de reputación, datos o
    disponibilidad de un profesor (US-15). El nombre puede ser parcial, p. ej.
    "garcia", "Gutierrez" o "rosa martinez".

    Args:
        nombre: Nombre completo o parcial del profesor a buscar.

    Returns:
        dict con "encontrado" (bool) y "profesores" (lista de fichas), o un
        mensaje si no hay coincidencias.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return {"encontrado": False, "mensaje": "Indica el nombre del profesor a buscar."}
    where_sql, params = _name_where("p.name", nombre)
    try:
        rows = await fetch_all(
            f"""
            SELECT p.name AS nombre, p.department AS departamento, p.degree AS grado,
                   p.bio AS biografia, p.email AS correo, p.availability AS disponibilidad,
                   COUNT(r.id) AS num_resenas,
                   ROUND(AVG(r.rating)::numeric, 2) AS rating_promedio
            FROM professors p
            LEFT JOIN reviews r ON r.professor_id = p.id
            WHERE {where_sql}
            GROUP BY p.id, p.name, p.department, p.degree, p.bio, p.email, p.availability
            ORDER BY p.name
            LIMIT 15
            """,
            params,
        )
    except Exception:
        logger.exception("buscar_profesor falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    # Deduplica por nombre (hay filas repetidas en los datos actuales).
    vistos: set[str] = set()
    profes: list[dict] = []
    for row in rows:
        clave = row["nombre"].strip().lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        profes.append(row)

    if not profes:
        return {
            "encontrado": False,
            "mensaje": f"No se encontró ningún profesor que coincida con '{nombre}'.",
        }
    return {"encontrado": True, "coincidencias": len(profes), "profesores": profes}


async def resenas_de_profesor(nombre: str) -> dict:
    """Devuelve las reseñas de estudiantes sobre un profesor y su rating promedio.

    Úsala cuando el estudiante quiera VER las opiniones/reseñas concretas de un
    profesor (US-15/US-21), no solo su ficha. Presenta las reseñas como
    percepciones de estudiantes, no como un hecho oficial.

    Args:
        nombre: Nombre completo o parcial del profesor.

    Returns:
        dict con el profesor, rating promedio, número de reseñas y la lista de
        reseñas (rating y comentario).
    """
    nombre = (nombre or "").strip()
    if not nombre:
        return {"encontrado": False, "mensaje": "Indica el nombre del profesor."}
    where_sql, params = _name_where("p.name", nombre)
    try:
        rows = await fetch_all(
            f"""
            SELECT p.name AS profesor, r.rating, r.comment AS comentario
            FROM reviews r
            JOIN professors p ON p.id = r.professor_id
            WHERE {where_sql}
            ORDER BY p.name, r.created_at DESC
            """,
            params,
        )
    except Exception:
        logger.exception("resenas_de_profesor falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    if not rows:
        return {
            "encontrado": False,
            "mensaje": f"No hay reseñas registradas para un profesor que coincida con '{nombre}'.",
        }

    # Agrupa por profesor (por si el nombre parcial coincide con varios).
    por_profesor: dict[str, list[dict]] = {}
    for row in rows:
        por_profesor.setdefault(row["profesor"], []).append(
            {"rating": row["rating"], "comentario": row["comentario"]}
        )

    resultado = []
    for profesor, resenas in por_profesor.items():
        promedio = round(sum(x["rating"] for x in resenas) / len(resenas), 2)
        resultado.append(
            {
                "profesor": profesor,
                "rating_promedio": promedio,
                "num_resenas": len(resenas),
                "resenas": resenas,
            }
        )
    return {"encontrado": True, "profesores": resultado}


async def listar_cursos(nivel: str = "", tipo: str = "") -> dict:
    """Lista cursos de la malla, opcionalmente filtrados por nivel y/o tipo.

    Úsala para "qué cursos hay en el nivel/ciclo N" o "cursos electivos" (US-18).

    Args:
        nivel: Nivel/ciclo a filtar: "1" a "10", o "ELE" para electivos. Vacío = todos.
        tipo: "obligatorio" o "electivo". Vacío = ambos.

    Returns:
        dict con la cantidad y la lista de cursos (código, nombre, nivel, créditos,
        dificultad 1-5 y tipo).
    """
    conds: list[str] = []
    params: dict[str, str] = {}
    nivel = (nivel or "").strip()
    tipo = (tipo or "").strip().lower()
    if nivel:
        conds.append("level = :nivel")
        params["nivel"] = nivel
    if tipo:
        conds.append("course_type = :tipo")
        params["tipo"] = tipo
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    try:
        rows = await fetch_all(
            f"""
            SELECT code AS codigo, name AS nombre, level AS nivel, credits AS creditos,
                   difficulty AS difficulty, course_type AS tipo
            FROM courses
            {where}
            ORDER BY CASE WHEN level ~ '^[0-9]+$' THEN level::int ELSE 99 END, code
            LIMIT 200
            """,
            params,
        )
    except Exception:
        logger.exception("listar_cursos falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    if not rows:
        return {
            "encontrado": False,
            "mensaje": "No se encontraron cursos con esos criterios.",
            "filtros": {"nivel": nivel or None, "tipo": tipo or None},
        }
    cursos = [_con_etiqueta_dificultad(r) for r in rows]
    return {"encontrado": True, "cantidad": len(cursos), "cursos": cursos}


async def detalle_curso(curso: str) -> dict:
    """Devuelve el detalle de un curso por su código o nombre.

    Incluye nivel, créditos, dificultad (1-5), tipo (obligatorio/electivo),
    prerrequisitos (por nombre) y el profesor asignado si lo hay. Úsala para
    consultar la dificultad de un curso (US-16) o su información general.

    Args:
        curso: Código exacto (p. ej. "650059") o nombre/parte del nombre
            (p. ej. "Estructuras de Datos I").

    Returns:
        dict con el/los curso(s) que coincidan.
    """
    curso = (curso or "").strip()
    if not curso:
        return {"encontrado": False, "mensaje": "Indica el código o nombre del curso."}
    try:
        rows = await fetch_all(
            """
            SELECT c.code AS codigo, c.name AS nombre, c.level AS nivel,
                   c.credits AS creditos, c.difficulty AS difficulty,
                   c.course_type AS tipo, c.prerequisites AS prerrequisitos,
                   p.name AS profesor
            FROM courses c
            LEFT JOIN professors p ON p.id = c.professor_id
            WHERE lower(c.code) = lower(:q) OR """ + _norm("c.name") + " LIKE " + _norm(":like") + """
            ORDER BY (lower(c.code) = lower(:q)) DESC, c.name
            LIMIT 5
            """,
            {"q": curso, "like": f"%{curso}%"},
        )
    except Exception:
        logger.exception("detalle_curso falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    if not rows:
        return {
            "encontrado": False,
            "mensaje": f"No se encontró un curso con código o nombre '{curso}'.",
        }
    cursos = [_con_etiqueta_dificultad(r) for r in rows]
    return {"encontrado": True, "coincidencias": len(cursos), "cursos": cursos}


async def prerrequisitos_de(curso: str) -> dict:
    """Devuelve los prerrequisitos de un curso y, si aplica, la cadena completa.

    Úsala para "qué necesito para llevar X" (US-17). Los prerrequisitos se guardan
    por NOMBRE de curso. Resuelve también los prerrequisitos de los prerrequisitos
    (la cadena) hasta agotarla, para poder explicarla al estudiante.

    Args:
        curso: Código exacto o nombre/parte del nombre del curso.

    Returns:
        dict con los prerrequisitos directos y la cadena resuelta.
    """
    curso = (curso or "").strip()
    if not curso:
        return {"encontrado": False, "mensaje": "Indica el código o nombre del curso."}
    try:
        base = await fetch_all(
            """
            SELECT c.name AS nombre, c.prerequisites AS prerrequisitos
            FROM courses c
            WHERE lower(c.code) = lower(:q) OR """ + _norm("c.name") + " LIKE " + _norm(":like") + """
            ORDER BY (lower(c.code) = lower(:q)) DESC, c.name
            LIMIT 1
            """,
            {"q": curso, "like": f"%{curso}%"},
        )
        if not base:
            return {
                "encontrado": False,
                "mensaje": f"No se encontró un curso con código o nombre '{curso}'.",
            }
        nombre = base[0]["nombre"]
        directos = list(base[0]["prerrequisitos"] or [])

        # Resuelve la cadena (prereqs de prereqs) por nombre, evitando ciclos.
        cadena: dict[str, list[str]] = {}
        visitados: set[str] = set()
        frontera = list(directos)
        while frontera:
            siguiente: list[str] = []
            for req in frontera:
                clave = req.strip().lower()
                if clave in visitados:
                    continue
                visitados.add(clave)
                filas = await fetch_all(
                    "SELECT prerequisites AS pr FROM courses "
                    f"WHERE {_norm('name')} = {_norm(':n')} LIMIT 1",
                    {"n": req.strip()},
                )
                sub = list(filas[0]["pr"]) if filas and filas[0]["pr"] else []
                cadena[req] = sub
                siguiente.extend(sub)
            frontera = siguiente
    except Exception:
        logger.exception("prerrequisitos_de falló")
        return {"encontrado": False, "error": _ERROR_MSG}

    return {
        "encontrado": True,
        "curso": nombre,
        "prerrequisitos_directos": directos,
        "cadena": cadena,
        "sin_prerrequisitos": not directos,
    }
