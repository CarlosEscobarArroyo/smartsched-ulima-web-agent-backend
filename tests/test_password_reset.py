"""Tests de restablecimiento de contraseña (US-25): forgot-password y reset-password."""

from unittest.mock import patch

from tests.conftest import make_user

FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
LOGIN_URL = "/api/v1/auth/login"


async def test_forgot_password_unknown_email_returns_200(client, db_session):
    """Siempre 200 — no se revela si el email existe."""
    resp = await client.post(FORGOT_URL, json={"email": "nadie@ulima.edu.pe"})
    assert resp.status_code == 200


async def test_forgot_password_known_email_returns_200(client, db_session):
    """Email registrado también devuelve 200."""
    await make_user(db_session)
    with patch("app.domains.auth.service.send_reset_email"):
        resp = await client.post(FORGOT_URL, json={"email": "alumno@ulima.edu.pe"})
    assert resp.status_code == 200


async def test_forgot_password_sends_email(client, db_session):
    """El servicio llama a send_reset_email con el correo del usuario."""
    await make_user(db_session)
    with patch("app.domains.auth.service.send_reset_email") as mock_send:
        await client.post(FORGOT_URL, json={"email": "alumno@ulima.edu.pe"})
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[0][0] == "alumno@ulima.edu.pe"
    assert "/reset-password?token=" in call_args[0][1]


async def test_reset_password_ok(client, db_session):
    """Token válido → contraseña actualizada, login con nueva contraseña funciona."""
    await make_user(db_session)

    captured: list[str] = []
    def capture(email: str, link: str) -> None:
        captured.append(link)

    with patch("app.domains.auth.service.send_reset_email", side_effect=capture):
        await client.post(FORGOT_URL, json={"email": "alumno@ulima.edu.pe"})

    token = captured[0].split("token=")[1]
    resp = await client.post(RESET_URL, json={"token": token, "new_password": "NuevaClave123"})
    assert resp.status_code == 200

    login = await client.post(LOGIN_URL, json={"email": "alumno@ulima.edu.pe", "password": "NuevaClave123"})
    assert login.status_code == 200


async def test_reset_password_invalid_token(client, db_session):
    """Token inexistente → 400."""
    resp = await client.post(RESET_URL, json={"token": "token-falso", "new_password": "NuevaClave123"})
    assert resp.status_code == 400


async def test_reset_password_token_reuse(client, db_session):
    """Usar el mismo token dos veces → el segundo intento falla con 400."""
    await make_user(db_session)

    captured: list[str] = []
    def capture(email: str, link: str) -> None:
        captured.append(link)

    with patch("app.domains.auth.service.send_reset_email", side_effect=capture):
        await client.post(FORGOT_URL, json={"email": "alumno@ulima.edu.pe"})

    token = captured[0].split("token=")[1]
    await client.post(RESET_URL, json={"token": token, "new_password": "Clave1111"})
    resp2 = await client.post(RESET_URL, json={"token": token, "new_password": "Clave2222"})
    assert resp2.status_code == 400


async def test_reset_password_short_password(client, db_session):
    """Contraseña menor a 6 caracteres → 422."""
    resp = await client.post(RESET_URL, json={"token": "cualquier-token", "new_password": "abc"})
    assert resp.status_code == 422
