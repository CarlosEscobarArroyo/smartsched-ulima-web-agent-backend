"""Cliente de email vía Resend (US-25). Si no hay API key, imprime el link en logs (dev)."""

import logging

import resend

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
  <p style="color:#888;font-size:13px">Este enlace expira en 60 minutos. Si no solicitaste esto, ignora este correo.</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#aaa;font-size:12px">SmartSched ULIMA — Universidad de Lima</p>
</body>
</html>
"""


def send_reset_email(to_email: str, reset_link: str) -> None:
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning("[DEV] Resend no configurado. Link de reset para %s: %s", to_email, reset_link)
        return

    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Restablecer contraseña — SmartSched ULIMA",
        "html": _HTML_TEMPLATE.format(reset_link=reset_link),
    })
