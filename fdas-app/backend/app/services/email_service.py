from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


logger = logging.getLogger(__name__)

SMTP_ENVIRONMENT_KEYS = {
    "FDAS_SMTP_HOST",
    "FDAS_SMTP_PORT",
    "FDAS_SMTP_USERNAME",
    "FDAS_SMTP_PASSWORD",
    "FDAS_SMTP_FROM_EMAIL",
    "FDAS_SMTP_FROM_NAME",
    "FDAS_SMTP_USE_TLS",
}
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_TIMEOUT_SECONDS = 10
APPROVAL_EMAIL_SUBJECT = "FDAS Account Approved"
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool
    configured: bool


@dataclass(frozen=True)
class EmailDeliveryResult:
    sent: bool
    message: str


@dataclass(frozen=True)
class ApprovalEmailContent:
    subject: str
    text_body: str
    html_body: str


def _read_local_environment_file() -> dict[str, str]:
    """Read only the optional SMTP keys from the ignored backend/.env file."""
    environment_path = BACKEND_DIRECTORY / ".env"
    if not environment_path.is_file():
        return {}

    values: dict[str, str] = {}
    try:
        for raw_line in environment_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key not in SMTP_ENVIRONMENT_KEYS:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            values[key] = value
    except OSError:
        logger.warning("Optional SMTP configuration file could not be read.")
    return values


def _parse_boolean(value: str, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


def load_smtp_settings() -> SmtpSettings:
    file_values = _read_local_environment_file()

    def setting(name: str, default: str = "") -> str:
        return os.getenv(name, file_values.get(name, default)).strip()

    host = setting("FDAS_SMTP_HOST")
    from_email = setting("FDAS_SMTP_FROM_EMAIL")
    username = setting("FDAS_SMTP_USERNAME")
    password = setting("FDAS_SMTP_PASSWORD")
    try:
        port = int(setting("FDAS_SMTP_PORT", str(DEFAULT_SMTP_PORT)))
    except ValueError:
        port = 0

    credentials_complete = bool(username) == bool(password)
    configured = bool(host and from_email and 0 < port <= 65535 and credentials_complete)
    return SmtpSettings(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
        from_name=setting("FDAS_SMTP_FROM_NAME", "FDAS") or "FDAS",
        use_tls=_parse_boolean(setting("FDAS_SMTP_USE_TLS", "true"), True),
        configured=configured,
    )


def build_approval_email(
    *,
    operator_name: str,
    login_id: str,
    department_name: str | None,
) -> ApprovalEmailContent:
    department_line = f"\nDepartment:\n{department_name}\n" if department_name else ""
    text_body = (
        f"Hello {operator_name},\n\n"
        "Your FDAS operator account has been approved by the administrator.\n\n"
        "You can now sign in using the email/login ID you registered with and "
        "the password you created during registration.\n\n"
        f"Login ID:\n{login_id}\n"
        f"{department_line}\n"
        "Account Status:\nApproved\n\n"
        "For security, your password is never included in email messages.\n\n"
        "Regards,\nFDAS Administration"
    )

    safe_name = html.escape(operator_name)
    safe_login_id = html.escape(login_id)
    department_html = ""
    if department_name:
        department_html = (
            '<tr><td style="padding:8px 0;color:#6f5b52;">Department</td>'
            f'<td style="padding:8px 0;font-weight:700;">{html.escape(department_name)}</td></tr>'
        )
    html_body = f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;background:#f9f3ed;font-family:Arial,sans-serif;color:#4a2b0f;">
    <div style="max-width:600px;margin:24px auto;background:#ffffff;border:1px solid #eadbd4;border-radius:12px;overflow:hidden;">
      <div style="background:#c4533a;color:#ffffff;padding:22px 28px;">
        <div style="font-size:24px;font-weight:700;">FDAS</div>
        <div style="margin-top:4px;font-size:14px;">Face Detection Attendance System</div>
      </div>
      <div style="padding:28px;line-height:1.6;">
        <p>Hello {safe_name},</p>
        <p>Your FDAS operator account has been approved by the administrator.</p>
        <p>You can now sign in using the email/login ID you registered with and the password you created during registration.</p>
        <table style="width:100%;border-collapse:collapse;background:#fff8f3;padding:12px;">
          <tr><td style="padding:8px 0;color:#6f5b52;">Login ID</td><td style="padding:8px 0;font-weight:700;">{safe_login_id}</td></tr>
          {department_html}
          <tr><td style="padding:8px 0;color:#6f5b52;">Account Status</td><td style="padding:8px 0;font-weight:700;color:#065f46;">Approved</td></tr>
        </table>
        <p style="margin-top:22px;color:#6f5b52;">For security, your password is never included in email messages.</p>
        <p>Regards,<br><strong>FDAS Administration</strong></p>
      </div>
    </div>
  </body>
</html>
"""
    return ApprovalEmailContent(
        subject=APPROVAL_EMAIL_SUBJECT,
        text_body=text_body,
        html_body=html_body,
    )


def send_approval_email(
    *,
    operator_name: str,
    recipient_email: str,
    department_name: str | None,
) -> EmailDeliveryResult:
    settings = load_smtp_settings()
    if not settings.configured:
        return EmailDeliveryResult(
            sent=False,
            message="Approval email unavailable because SMTP is not configured.",
        )

    try:
        content = build_approval_email(
            operator_name=operator_name,
            login_id=recipient_email,
            department_name=department_name,
        )
        message = EmailMessage()
        message["Subject"] = content.subject
        message["From"] = f"{settings.from_name} <{settings.from_email}>"
        message["To"] = recipient_email
        message.set_content(content.text_body)
        message.add_alternative(content.html_body, subtype="html")

        with smtplib.SMTP(settings.host, settings.port, timeout=DEFAULT_SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            if settings.use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if settings.username:
                smtp.login(settings.username, settings.password)
            smtp.send_message(message)
    except Exception as exc:  # SMTP/network failures must not undo account approval.
        logger.error("Approval email delivery failed (%s).", type(exc).__name__)
        return EmailDeliveryResult(
            sent=False,
            message="Approval email could not be sent.",
        )

    return EmailDeliveryResult(
        sent=True,
        message="Approval email sent successfully.",
    )
