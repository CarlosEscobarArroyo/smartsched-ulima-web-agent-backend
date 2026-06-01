"""Cliente de email vía SMTP de Gmail (US-25).

Usa `smtplib` (stdlib) + STARTTLS en el puerto 587. Requiere una cuenta de Gmail
y una **contraseña de aplicación** (no la contraseña normal): se generan en
https://myaccount.google.com/apppasswords con la verificación en 2 pasos activada.

Si SMTP no está configurado (sin `smtp_user`/`smtp_password`), imprime el link en
los logs (modo dev), igual que antes.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<body style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;color:#1a1a1a">
  <h2 style="margin-bottom:8px">Restablecer contraseña</h2>
  <p style="color:#555">Recibimos una solicitud para restablecer la contraseña de tu cuenta en <strong>SmartSched ULIMA</strong>.</p>
  <p style="margin:24px 0">
    <a href="{reset_link}"
       style="background:#1a1a1a;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
      Restablecer contraseña
    </a>
  </p>
  <p style="color:#888;font-size:13px">Este enlace expira en {minutes} minutos. Si no solicitaste esto, ignora este correo.</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#aaa;font-size:12px">SmartSched ULIMA — Universidad de Lima</p>
</body>
</html>
"""

_TEXT_TEMPLATE = """\
Restablecer contraseña — SmartSched ULIMA

Recibimos una solicitud para restablecer la contraseña de tu cuenta.
Abre este enlace (expira en {minutes} minutos):

{reset_link}

Si no solicitaste esto, ignora este correo.
"""


def send_reset_email(to_email: str, reset_link: str) -> None:
    settings = get_settings()

    # Gmail muestra la app password en grupos separados por espacios; el login es
    # sin espacios. Limpiamos para tolerar ambos formatos en el .env.
    smtp_user = (settings.smtp_user or "").strip()
    smtp_password = (settings.smtp_password or "").replace(" ", "")

    if not smtp_user or not smtp_password:
        logger.warning(
            "[DEV] SMTP no configurado. Link de reset para %s: %s", to_email, reset_link
        )
        return

    minutes = settings.reset_token_expire_minutes

    message = EmailMessage()
    message["Subject"] = "Restablecer contraseña — SmartSched ULIMA"
    message["From"] = f"{settings.smtp_from_name} <{smtp_user}>"
    message["To"] = to_email
    message.set_content(_TEXT_TEMPLATE.format(reset_link=reset_link, minutes=minutes))
    message.add_alternative(
        _HTML_TEMPLATE.format(reset_link=reset_link, minutes=minutes), subtype="html"
    )

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        logger.info("Correo de restablecimiento enviado a %s", to_email)
    except Exception:
        logger.exception("Error al enviar correo de restablecimiento a %s", to_email)
        raise
