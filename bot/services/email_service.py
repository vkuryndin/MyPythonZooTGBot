import asyncio
import logging
import smtplib
from email.message import EmailMessage

from bot.config import settings


logger = logging.getLogger(__name__)


class EmailConfigurationError(RuntimeError):
    pass


def _validate_email_settings() -> None:
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
    try:
        logger.info("Sending email message to staff")

        await asyncio.to_thread(
            _send_email_sync,
            subject,
            body,
        )

        logger.info("Email message sent to staff")
    except Exception:
        logger.exception("Failed to send email message to staff")
        raise