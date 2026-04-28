import asyncio
import smtplib
from email.message import EmailMessage

from bot.config import settings


class EmailConfigurationError(RuntimeError):
    """Raised when email settings are not configured."""


def _validate_email_settings() -> None:
    """Validate required SMTP settings."""

    required_values = [
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_user,
        settings.smtp_password,
        settings.staff_email,
    ]

    if not all(required_values):
        raise EmailConfigurationError(
            "Email settings are not fully configured"
        )


def _send_email_sync(subject: str, body: str) -> None:
    """Send email synchronously via SMTP."""

    _validate_email_settings()

    message = EmailMessage()
    message["From"] = settings.smtp_user
    message["To"] = settings.staff_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(
        host=settings.smtp_host,
        port=settings.smtp_port,
        timeout=20,
    ) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


async def send_contact_email(subject: str, body: str) -> None:
    """Send contact email without blocking the bot event loop."""

    await asyncio.to_thread(_send_email_sync, subject, body)