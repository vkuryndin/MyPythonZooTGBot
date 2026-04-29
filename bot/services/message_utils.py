from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message


async def safe_delete_callback_message(callback: CallbackQuery) -> None:
    """Safely delete message related to callback."""

    if callback.message is None:
        return

    await safe_delete_message(callback.message)


async def safe_delete_message(message: Message | None) -> None:
    """Safely delete Telegram message."""

    if message is None:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def safe_delete_message_by_id(
    message: Message,
    message_id: int | None,
) -> None:
    """Safely delete message by id in the same chat."""

    if message_id is None:
        return

    try:
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=int(message_id),
        )
    except TelegramBadRequest:
        pass


async def safe_remove_keyboard(callback: CallbackQuery) -> None:
    """Safely remove inline keyboard from callback message."""

    if callback.message is None:
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


async def safe_delete_messages_by_ids(
    message: Message,
    message_ids: list[int],
) -> None:
    """Safely delete several messages by ids in the same chat."""

    for message_id in message_ids:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=message_id,
            )
        except TelegramBadRequest:
            pass