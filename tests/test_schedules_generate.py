"""Tests de US-07: POST /api/v1/schedules/generate.

Prueban el cableado HTTP + la adaptación del contrato del FE (strings `horarios`/
`blockedSlots`) sobre el generador puro: combinaciones válidas, bloqueos, restricciones
imposibles (200 con lista vacía), sin cursos (422) y truncamiento a MAX_OPTIONS.
"""

from fastapi.testclient import TestClient

from app.domains.schedules.service import MAX_OPTIONS
from app.main import app

client = TestClient(app)

URL = "/api/v1/schedules/generate"


def _section(sec_id: str, seccion: str, horarios: list[str]) -> dict:
    return {
        "id": sec_id,
        "seccion": seccion,
        "profesor": "DOCENTE X",
        "aula": "850014",
        "horarios": horarios,
    }


def _course(cid: str, name: str, sections: list[dict], selected: bool = True) -> dict:
    return {
        "id": cid,
        "code": cid,
        "name": name,
        "schedule": f"{len(sections)} secciones",
        "sections": sections,
        "selected": selected,
    }


def test_genera_una_combinacion_simple() -> None:
    payload = {
        "courses": [
            _course("c1", "Curso 1", [_section("c1-a", "100", ["LUN 08:00-10:00"])]),
            _course("c2", "Curso 2", [_section("c2-a", "200", ["MAR 08:00-10:00"])]),
        ],
        "blockedSlots": [],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["truncated"] is False
    assert len(body["options"]) == 1
    option = body["options"][0]
    assert len(option["courses"]) == 2
    # Cada curso trae la sección elegida en camelCase (contrato FE).
    ids = {c["id"]: c["selectedSection"]["id"] for c in option["courses"]}
    assert ids == {"c1": "c1-a", "c2": "c2-a"}


def test_dos_secciones_por_curso_generan_varias_opciones() -> None:
    payload = {
        "courses": [
            _course(
                "c1",
                "Curso 1",
                [
                    _section("c1-a", "100", ["LUN 08:00-10:00"]),
                    _section("c1-b", "101", ["LUN 10:00-12:00"]),
                ],
            ),
            _course("c2", "Curso 2", [_section("c2-a", "200", ["MAR 08:00-10:00"])]),
        ],
        "blockedSlots": [],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 200
    assert len(res.json()["options"]) == 2


def test_caso_analitica_ciberseguridad_da_dos_opciones() -> None:
    """Regresión (caso reportado por Carlos): un curso de 1 sección fija +
    otro con 4 secciones donde 2 chocan en JUE con la fija → deben quedar 2 opciones.

    853 (LUN/JUE 18-20) es fija. De Ciberseguridad: 751 (MIE 20-22, SAB 07-10) y
    753 (MAR 20-22, VIE 19-22) NO chocan; 754 y 755 (ambas JUE 19-22) SÍ chocan con
    el JUE 18-20 de la 853 y deben descartarse.
    """
    payload = {
        "courses": [
            _course(
                "650078",
                "ANALITICA DE NEGOCIOS",
                [_section("an-853", "853", ["LUN 18:00-20:00", "JUE 18:00-20:00"])],
            ),
            _course(
                "650065",
                "CIBERSEGURIDAD",
                [
                    _section("cy-751", "751", ["MIE 20:00-22:00", "SAB 07:00-10:00"]),
                    _section("cy-753", "753", ["MAR 20:00-22:00", "VIE 19:00-22:00"]),
                    _section("cy-754", "754", ["MIE 20:00-22:00", "JUE 19:00-22:00"]),
                    _section("cy-755", "755", ["MAR 20:00-22:00", "JUE 19:00-22:00"]),
                ],
            ),
        ],
        "blockedSlots": [],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 200
    options = res.json()["options"]
    assert len(options) == 2
    # Las secciones de Ciberseguridad elegidas son exactamente 751 y 753.
    chosen = {
        next(c["selectedSection"]["seccion"] for c in opt["courses"] if c["code"] == "650065")
        for opt in options
    }
    assert chosen == {"751", "753"}


def test_secciones_que_chocan_entre_cursos_no_generan_opcion() -> None:
    payload = {
        "courses": [
            _course("c1", "Curso 1", [_section("c1-a", "100", ["LUN 08:00-10:00"])]),
            _course("c2", "Curso 2", [_section("c2-a", "200", ["LUN 09:00-11:00"])]),
        ],
        "blockedSlots": [],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 200
    assert res.json()["options"] == []


def test_blocked_slot_descarta_seccion() -> None:
    # Única sección de c1 cae en Lun 08:00-09:00; bloqueamos "Lun-8" → imposible.
    payload = {
        "courses": [
            _course("c1", "Curso 1", [_section("c1-a", "100", ["LUN 08:00-09:00"])]),
        ],
        "blockedSlots": ["Lun-8"],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 200
    assert res.json()["options"] == []


def test_sin_cursos_seleccionados_devuelve_422() -> None:
    payload = {
        "courses": [
            _course("c1", "Curso 1", [_section("c1-a", "100", ["LUN 08:00-10:00"])], selected=False)
        ],
        "blockedSlots": [],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 422


def test_curso_seleccionado_sin_secciones_validas_no_genera() -> None:
    payload = {
        "courses": [
            _course("c1", "Curso 1", [_section("c1-a", "100", ["LUN 08:00-10:00"])]),
            _course("c2", "Curso 2", [_section("c2-a", "200", [])]),
        ],
        "blockedSlots": [],
    }
    res = client.post(URL, json=payload)
    assert res.status_code == 200
    assert res.json()["options"] == []


def test_trunca_en_max_options() -> None:
    # 3 cursos x 3 secciones, cada curso en su propio día → sin choques → 27 combinaciones.
    courses = []
    for ci, day in enumerate(["LUN", "MAR", "MIE"]):
        sections = [
            _section(f"c{ci}-{h}", f"{h}", [f"{day} {h:02d}:00-{h:02d}:30"]) for h in (8, 9, 10)
        ]
        courses.append(_course(f"c{ci}", f"Curso {ci}", sections))
    res = client.post(URL, json={"courses": courses, "blockedSlots": []})
    assert res.status_code == 200
    body = res.json()
    assert body["truncated"] is True
    assert len(body["options"]) == MAX_OPTIONS
