"""PRUEBA UNITARIA — `_parse_horario()` (6 casos).

Método bajo prueba: ``app/domains/schedules/service.py`` → ``_parse_horario``.

Una prueba unitaria valida UN método de forma aislada, sin dependencias externas.
`_parse_horario` convierte un string del frontend ("MIE 11:00-13:00") en un
``TimeBlock`` estructurado, o devuelve ``None`` si el texto no parsea o el rango es
inválido. Es una función pura: misma entrada, misma salida.

Los 6 casos cubren las clases relevantes: parseo correcto, día inválido, formato
irreconocible, hora fuera de rango (valor límite) y el rango invertido inicio>=fin.
"""

from datetime import time

from app.domains.schedules.service import _parse_horario

# Días: LUN=0, MAR=1, MIE=2, JUE=3, VIE=4, SAB=5, DOM=6.


# Caso 1 — string bien formado → TimeBlock con día y horas correctos.
def test_horario_valido_devuelve_timeblock() -> None:
    tb = _parse_horario("MIE 11:00-13:00")
    assert tb is not None
    assert tb.day == 2
    assert tb.start == time(11, 0)
    assert tb.end == time(13, 0)


# Caso 2 — día en minúsculas y con aula extra: se normaliza igual.
def test_horario_minusculas_con_aula() -> None:
    tb = _parse_horario("lun 08:00-10:00 Aula 850")
    assert tb is not None
    assert tb.day == 0
    assert tb.start == time(8, 0)


# Caso 3 — día desconocido → None.
def test_dia_invalido_devuelve_none() -> None:
    assert _parse_horario("XXX 08:00-10:00") is None


# Caso 4 — texto sin el formato esperado → None.
def test_formato_irreconocible_devuelve_none() -> None:
    assert _parse_horario("no es un horario") is None


# Caso 5 (VALOR LÍMITE) — hora fuera de rango (25:00): `time()` lanza y se captura → None.
def test_hora_fuera_de_rango_devuelve_none() -> None:
    assert _parse_horario("MAR 25:00-26:00") is None


# Caso 6 — rango invertido (inicio >= fin) → None.
def test_inicio_mayor_o_igual_que_fin_devuelve_none() -> None:
    assert _parse_horario("JUE 13:00-11:00") is None
