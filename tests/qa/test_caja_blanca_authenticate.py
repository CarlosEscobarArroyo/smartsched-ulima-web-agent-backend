"""PRUEBA DE CAJA BLANCA — `authenticate()` (login + bloqueo por intentos).

Módulo bajo prueba: ``app/domains/auth/service.py`` → ``authenticate`` (y su helper
``_is_locked``, que forma parte del mismo camino de decisión).

------------------------------------------------------------------------------
¿Por qué caja blanca?
------------------------------------------------------------------------------
La caja blanca (prueba estructural) diseña los casos MIRANDO el código para
recorrer cada rama. `authenticate` implementa la regla de negocio de seguridad
US-24 CA-2 (bloqueo tras `max_login_attempts` fallos), así que interesa ejercitar
todos sus caminos: éxito, credenciales inválidas, incremento del contador,
bloqueo al alcanzar el tope y rechazo de una cuenta ya bloqueada.

------------------------------------------------------------------------------
Complejidad ciclomática (McCabe)
------------------------------------------------------------------------------
Se cuenta 1 + (número de puntos de decisión) en el cuerpo de `authenticate`:

    D1  if user is None or not user.is_active:        (+1 por el `or`)  → 2
    D2  if _is_locked(user, now):                     (cuenta bloqueada → 423)
    D3  if not verify_password(...):                  (password incorrecto)
    D4  if user.failed_attempts >= max_login_attempts:(alcanza el tope → bloquea)

    Complejidad ciclomática V(G) = 1 + 5 = 6   →   6 > 4  ✔
    (verificado con `radon cc`: authenticate = 6)

Si además se cuenta el helper `_is_locked` que invoca (2 decisiones propias: la
comparación con None y el ajuste de zona horaria), el flujo completo llega a 8.
En cualquiera de las dos lecturas supera el umbral de 4.

Cada test de abajo indica, en su docstring, el/los punto(s) de decisión que cubre.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.domains.auth.service import authenticate
from app.domains.users.models import User, UserRole
from tests.conftest import make_user

EMAIL = "alumno@ulima.edu.pe"
PASSWORD = "Alumno123"


# ---------------------------------------------------------------------------
# Camino feliz: credenciales válidas → token y reseteo del contador.
# ---------------------------------------------------------------------------


async def test_login_valido_devuelve_token(db_session) -> None:
    """Todos los `if` en falso → emite token (rama principal, D5 en False)."""
    await make_user(db_session, email=EMAIL, password=PASSWORD)
    result = await authenticate(db_session, EMAIL, PASSWORD)
    assert result.access_token
    assert result.user.email == EMAIL


async def test_login_valido_resetea_contador_de_fallos(db_session) -> None:
    """Camino de éxito con `failed_attempts` previo > 0: debe volver a 0."""
    user = await make_user(db_session, email=EMAIL, password=PASSWORD)
    user.failed_attempts = 2
    await db_session.commit()

    await authenticate(db_session, EMAIL, PASSWORD)
    assert user.failed_attempts == 0
    assert user.locked_until is None


# ---------------------------------------------------------------------------
# D1 — usuario inexistente o inactivo → 401.
# ---------------------------------------------------------------------------


async def test_usuario_inexistente_devuelve_401(db_session) -> None:
    """Camino D1 (user is None): sin usuario en BD → 401."""
    with pytest.raises(HTTPException) as exc:
        await authenticate(db_session, "nadie@ulima.edu.pe", PASSWORD)
    assert exc.value.status_code == 401


async def test_usuario_inactivo_devuelve_401(db_session) -> None:
    """Camino D1 (not user.is_active): cuenta desactivada → 401."""
    await make_user(db_session, email=EMAIL, password=PASSWORD, is_active=False)
    with pytest.raises(HTTPException) as exc:
        await authenticate(db_session, EMAIL, PASSWORD)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# D5 + D6 — password incorrecto: incrementa contador y, al llegar al tope, bloquea.
# ---------------------------------------------------------------------------


async def test_password_incorrecto_incrementa_y_devuelve_401(db_session) -> None:
    """Camino D5 (verify_password False) con D6 en False: 401 e incrementa."""
    user = await make_user(db_session, email=EMAIL, password=PASSWORD)
    with pytest.raises(HTTPException) as exc:
        await authenticate(db_session, EMAIL, "malísima")
    assert exc.value.status_code == 401
    assert user.failed_attempts == 1


async def test_tres_intentos_fallidos_bloquean_con_423(db_session) -> None:
    """Camino D6 (failed_attempts >= max_login_attempts): al 3er fallo → 423,
    se fija `locked_until` y el contador se resetea a 0."""
    user = await make_user(db_session, email=EMAIL, password=PASSWORD)

    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            await authenticate(db_session, EMAIL, "malísima")
        assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        await authenticate(db_session, EMAIL, "malísima")
    assert exc.value.status_code == 423
    assert user.locked_until is not None
    assert user.failed_attempts == 0


# ---------------------------------------------------------------------------
# D2 — cuenta ya bloqueada: rechaza sin siquiera verificar el password.
# ---------------------------------------------------------------------------


async def test_cuenta_bloqueada_rechaza_incluso_con_password_correcto(db_session) -> None:
    """Camino D2 (_is_locked True): con `locked_until` en el futuro, ni el
    password correcto pasa → 423 (D5 nunca se evalúa)."""
    user = User(
        id="00000000-0000-0000-0000-0000000000aa",
        email=EMAIL,
        name="Alumno Demo",
        password_hash=hash_password(PASSWORD),
        role=UserRole.STUDENT.value,
        is_active=True,
        locked_until=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await authenticate(db_session, EMAIL, PASSWORD)
    assert exc.value.status_code == 423
