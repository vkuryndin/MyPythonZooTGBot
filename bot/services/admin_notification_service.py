import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Update

from bot.config import settings


logger = logging.getLogger(__name__)

HANDLER_ALERT_COOLDOWN_SECONDS = 300

_last_handler_alert_at = 0.0
_suppressed_handler_alerts = 0


def limit_alert_text(value: str, max_length: int = 500) -> str:
    text = value.strip()

    if not text:
        return "нет подробного сообщения"

    # Telegram alerts should stay short. Full details remain in server logs.
    if len(text) <= max_length:
        return text

    return f"{text[:max_length]}…"


def get_update_summary(update: Update | None) -> dict[str, str]:
    if update is None:
        return {
            "update_id": "неизвестно",
            "update_type": "неизвестно",
            "user_id": "неизвестно",
            "username": "не указан",
            "chat_id": "неизвестно",
        }

    update_id = str(update.update_id)
    update_type = "другое"
    user_id = "неизвестно"
    username = "не указан"
    chat_id = "неизвестно"

    if update.message is not None:
        update_type = "message"

        if update.message.from_user is not None:
            user_id = str(update.message.from_user.id)
            if update.message.from_user.username:
                username = f"@{update.message.from_user.username}"

        chat_id = str(update.message.chat.id)

    elif update.callback_query is not None:
        update_type = "callback_query"

        user_id = str(update.callback_query.from_user.id)
        if update.callback_query.from_user.username:
            username = f"@{update.callback_query.from_user.username}"

        callback_message = update.callback_query.message
        if callback_message is not None and hasattr(callback_message, "chat"):
            chat_id = str(callback_message.chat.id)

    elif update.edited_message is not None:
        update_type = "edited_message"

        if update.edited_message.from_user is not None:
            user_id = str(update.edited_message.from_user.id)
            if update.edited_message.from_user.username:
                username = f"@{update.edited_message.from_user.username}"

        chat_id = str(update.edited_message.chat.id)

    elif update.inline_query is not None:
        update_type = "inline_query"

        user_id = str(update.inline_query.from_user.id)
        if update.inline_query.from_user.username:
            username = f"@{update.inline_query.from_user.username}"

    return {
        "update_id": update_id,
        "update_type": update_type,
        "user_id": user_id,
        "username": username,
        "chat_id": chat_id,
    }


def should_send_handler_alert() -> tuple[bool, int]:
    global _last_handler_alert_at
    global _suppressed_handler_alerts

    now = time.monotonic()

    # Avoid alert storms when the same broken handler fails repeatedly.
    if now - _last_handler_alert_at < HANDLER_ALERT_COOLDOWN_SECONDS:
        _suppressed_handler_alerts += 1
        return False, _suppressed_handler_alerts

    suppressed_count = _suppressed_handler_alerts
    _suppressed_handler_alerts = 0
    _last_handler_alert_at = now

    return True, suppressed_count


async def notify_admin_about_critical_startup_error(
    bot: Bot,
    stage: str,
    error: Exception,
) -> None:
    if settings.admin_chat_id <= 0:
        logger.warning("ADMIN_CHAT_ID is not configured, startup alert was not sent")
        return

    error_type = type(error).__name__
    error_message = limit_alert_text(str(error))

    text = (
        "🚨 Бот не смог запуститься\n\n"
        f"Этап: {stage}\n"
        f"Тип ошибки: {error_type}\n"
        f"Сообщение: {error_message}\n\n"
        "Что проверить:\n"
        "1. PostgreSQL запущен и доступен по сети;\n"
        "2. Redis запущен и доступен;\n"
        "3. DB_HOST, DB_PORT, DB_NAME, DB_USER и DB_PASSWORD корректны;\n"
        "4. REDIS_URL указан правильно;\n"
        "5. если запуск через Docker Compose — DB_HOST должен быть postgres;\n"
        "6. если запуск локально — DB_HOST должен указывать на доступный PostgreSQL."
    )

    try:
        await bot.send_message(
            chat_id=settings.admin_chat_id,
            text=text,
            parse_mode=None,
        )
        logger.info("Startup failure alert sent to admin")
    except TelegramAPIError:
        logger.exception("Failed to send startup failure alert to admin")


async def notify_admin_about_handler_error(
    bot: Bot,
    update: Update | None,
    error: Exception,
) -> None:
    if settings.admin_chat_id <= 0:
        logger.warning("ADMIN_CHAT_ID is not configured, handler alert was not sent")
        return

    should_send, suppressed_count = should_send_handler_alert()

    if not should_send:
        logger.warning(
            "Handler error alert suppressed by cooldown suppressed_count=%s",
            suppressed_count,
        )
        return

    # Do not include message text or callback.data here:
    # handler alerts are for diagnostics, not for exposing user input.
    update_summary = get_update_summary(update)
    error_type = type(error).__name__
    error_message = limit_alert_text(str(error))

    suppressed_text = ""

    if suppressed_count > 0:
        suppressed_text = (
            f"\n\nЗа время cooldown было подавлено похожих alert-ов: "
            f"{suppressed_count}"
        )

    # Send only operational details. Secrets, passwords and full tracebacks
    # must stay out of Telegram messages.
    text = (
        "🚨 Ошибка в handler-е бота\n\n"
        f"Тип update: {update_summary['update_type']}\n"
        f"Update ID: {update_summary['update_id']}\n"
        f"User ID: {update_summary['user_id']}\n"
        f"Username: {update_summary['username']}\n"
        f"Chat ID: {update_summary['chat_id']}\n\n"
        f"Тип ошибки: {error_type}\n"
        f"Сообщение: {error_message}\n"
        f"{suppressed_text}\n\n"
        "Полный traceback смотри в логах сервера.\n"
        "Текст сообщения пользователя и callback.data в alert не выводятся."
    )

    try:
        await bot.send_message(
            chat_id=settings.admin_chat_id,
            text=text,
            parse_mode=None,
        )
        logger.info("Handler error alert sent to admin")
    except TelegramAPIError:
        logger.exception("Failed to send handler error alert to admin")