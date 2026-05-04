import logging

from aiogram import Router
from aiogram.types import ErrorEvent, Update, Message

from bot.services.admin_notification_service import notify_admin_about_handler_error


router = Router()
logger = logging.getLogger(__name__)


async def send_safe_user_error_message(update: Update) -> None:
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(
                "Что-то пошло не так. Попробуй вернуться в меню через /start 🐾",
                show_alert=True,
            )
            return

        if update.message is not None:
            await update.message.answer(
                "Что-то пошло не так. Попробуй вернуться в меню через /start 🐾"
            )
            return

        if update.edited_message is not None:
            await update.edited_message.answer(
                "Что-то пошло не так. Попробуй вернуться в меню через /start 🐾"
            )
            return

    except Exception:
        logger.exception("Failed to send safe error message to user")


@router.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    logger.exception(
        "Unhandled handler error update_id=%s error_type=%s",
        event.update.update_id if event.update else None,
        type(event.exception).__name__,
        exc_info=event.exception,
    )

    await notify_admin_about_handler_error(
        bot=event.update.bot,
        update=event.update,
        error=event.exception,
    )

    await send_safe_user_error_message(event.update)

    return True
