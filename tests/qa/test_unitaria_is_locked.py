"""PRUEBA UNITARIA — `_is_locked()` (5 casos).

Método bajo prueba: ``app/domains/auth/service.py`` → ``_is_locked``.

Una prueba unitaria valida UN método de forma aislada, sin dependencias externas
(sin BD, sin HTTP). Aquí se construye un ``User`` transitorio en memoria (nunca se
persiste) y se comprueba la salida booleana. Es el equivalente a un test JUnit puro.

`_is_locked(user, now)` decide si un usuario tiene un bloqueo vigente. La regla es:
    - Sin `locked_until` → no está bloqueado.
    - Con `locked_until` en el futuro → bloqueado.
    - Con `locked_until` en el pasado → ya no está bloqueado.
    - Si `locked_until` viene "naive" (sin tzinfo, como lo devuelve SQLite) se le
      asume UTC antes de comparar (valor límite de la lógica de zona horaria).

Los 5 casos cubren cada clase relevante, incluyendo las dos ramas del manejo de
zona horaria (aware vs. naive).
"""

from datetime import UTC, datetime, timedelta

from app.domains.auth.service import _is_locked
from app.domains.users.models import User, UserRole


def _user(locked_until) -> User:
    """`User` transitorio (en memoria) con solo lo que `_is_locked` necesita."""
    return User(
        id="00000000-0000-0000-0000-0000000000ff",
        email="x@ulima.edu.pe",
        name="X",
        password_hash="hash",
        role=UserRole.STUDENT.value,
        locked_until=locked_until,
    )


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


# Caso 1 — sin bloqueo (`locked_until is None`) → False.
def test_sin_locked_until_no_esta_bloqueado() -> None:
    assert _is_locked(_user(None), NOW) is False


# Caso 2 — bloqueo vigente (aware, en el futuro) → True.
def test_locked_until_futuro_esta_bloqueado() -> None:
    assert _is_locked(_user(NOW + timedelta(minutes=10)), NOW) is True


# Caso 3 — bloqueo expirado (aware, en el pasado) → False.
def test_locked_until_pasado_no_esta_bloqueado() -> None:
    assert _is_locked(_user(NOW - timedelta(minutes=10)), NOW) is False


# Caso 4 (LÍMITE tz) — `locked_until` naive en el futuro: se asume UTC → True.
def test_locked_until_naive_futuro_se_asume_utc() -> None:
    naive_future = (NOW + timedelta(minutes=10)).replace(tzinfo=None)
    assert _is_locked(_user(naive_future), NOW) is True


# Caso 5 (LÍMITE tz) — `locked_until` naive en el pasado: se asume UTC → False.
def test_locked_until_naive_pasado_se_asume_utc() -> None:
    naive_past = (NOW - timedelta(minutes=10)).replace(tzinfo=None)
    assert _is_locked(_user(naive_past), NOW) is False
