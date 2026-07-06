"""PRUEBA UNITARIA — `TimeBlock.overlaps()` (6 casos).

Método bajo prueba: ``app/integrations/generator/generator.py`` →
``TimeBlock.overlaps``.

Una prueba unitaria valida UN método de forma aislada, sin dependencias externas
(sin BD, sin HTTP). Es el equivalente a un test JUnit puro (sin Mockito): se le
dan entradas y se comprueba la salida.

`overlaps` decide si dos bloques de horario se cruzan. La regla es:
    mismo día  AND  inicio_A < fin_B  AND  inicio_B < fin_A

Se incluyen 6 casos que cubren las clases relevantes, incluyendo el valor límite
(bloques que se tocan justo en el borde, que NO deben considerarse solapados).
"""

from datetime import time

from app.integrations.generator.generator import TimeBlock

LUN, MAR = 0, 1


def _tb(day: int, start: str, end: str) -> TimeBlock:
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    return TimeBlock(day=day, start=time(sh, sm), end=time(eh, em))


# Caso 1 — mismo día, solapamiento parcial → True
def test_solapamiento_parcial_mismo_dia() -> None:
    a = _tb(LUN, "08:00", "10:00")
    b = _tb(LUN, "09:00", "11:00")
    assert a.overlaps(b) is True


# Caso 2 (VALOR LÍMITE) — mismo día, se tocan en el borde (10:00) → False
def test_bloques_que_se_tocan_en_el_borde_no_solapan() -> None:
    a = _tb(LUN, "08:00", "10:00")
    b = _tb(LUN, "10:00", "12:00")
    assert a.overlaps(b) is False


# Caso 3 — mismo día, un bloque contiene al otro → True
def test_un_bloque_contiene_al_otro() -> None:
    grande = _tb(LUN, "08:00", "12:00")
    chico = _tb(LUN, "09:00", "10:00")
    assert grande.overlaps(chico) is True
    assert chico.overlaps(grande) is True  # la relación es simétrica


# Caso 4 — mismo día, bloques disjuntos (separados) → False
def test_bloques_disjuntos_mismo_dia() -> None:
    a = _tb(LUN, "08:00", "10:00")
    b = _tb(LUN, "13:00", "15:00")
    assert a.overlaps(b) is False


# Caso 5 — mismo horario pero DÍAS distintos → False
def test_mismo_horario_distinto_dia_no_solapa() -> None:
    a = _tb(LUN, "08:00", "10:00")
    b = _tb(MAR, "08:00", "10:00")
    assert a.overlaps(b) is False


# Caso 6 — bloques idénticos → True
def test_bloques_identicos_solapan() -> None:
    a = _tb(LUN, "08:00", "10:00")
    b = _tb(LUN, "08:00", "10:00")
    assert a.overlaps(b) is True
