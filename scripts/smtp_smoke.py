"""Smoke test del envío de correo (US-25) vía SMTP de Gmail.

Verifica login SMTP + envío real usando el MISMO código de producción
(`app.integrations.email.client.send_reset_email`).

Uso:
    uv run python scripts/smtp_smoke.py [correo_destino]

Si no se pasa `correo_destino`, envía a la propia cuenta (SMTP_USER).
Requiere SMTP_USER + SMTP_PASSWORD (app password de Gmail) en el .env.
"""

import sys

from app.core.config import get_settings
from app.integrations.email.client import send_reset_email


def main() -> int:
    settings = get_settings()
    user = (settings.smtp_user or "").strip()
    password = (settings.smtp_password or "").replace(" ", "")

    if not user or not password:
        print("❌ Falta SMTP_USER y/o SMTP_PASSWORD en el .env.")
        return 1

    to_email = sys.argv[1] if len(sys.argv) > 1 else user
    masked = f"{password[:3]}…{password[-2:]} (len={len(password)})"

    print("── Configuración SMTP ──────────────────────────────")
    print(f"  Host : {settings.smtp_host}:{settings.smtp_port}")
    print(f"  User : {user}")
    print(f"  Pass : {masked}")
    print(f"  From : {settings.smtp_from_name} <{user}>")
    print(f"  Para : {to_email}")
    print("────────────────────────────────────────────────────")
    print("Enviando correo de prueba…")

    reset_link = f"{settings.frontend_url}/reset-password?token=SMOKE-TEST-DEMO"
    try:
        send_reset_email(to_email, reset_link)
    except Exception as exc:
        print(f"\n❌ Falló el envío: {type(exc).__name__}: {exc}")
        print(
            "\nPistas:\n"
            "  • 535 5.7.8 → usuario/app password incorrectos o 2FA no activado.\n"
            "  • La app password debe ser de la MISMA cuenta que SMTP_USER.\n"
            "  • Si la cuenta es de Workspace, el admin puede tener bloqueadas las app passwords."
        )
        return 1

    print(f"\n✅ Enviado a {to_email}. Revisa la bandeja de entrada (y spam).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
