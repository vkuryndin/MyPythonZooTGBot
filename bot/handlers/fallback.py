import asyncio

from aiogram import F, Router
from aiogram.types import Message

from bot.services.message_utils import safe_delete_message


router = Router()


@router.message(F.text)
async def unexpected_text_handler(message: Message) -> None:

    await safe_delete_message(message)

    warning_message = await message.answer(
        "Пожалуйста, используй кнопки меню 👇\n\n"
        "Доступные команды:\n"
        "/start — стартовый экран\n"
        "/help — справка\n"
        "/result — последний результат\n"
        "/cancel — отменить действие"
    )

    await asyncio.sleep(4)
    await safe_delete_message(warning_message)


@router.message()
async def unexpected_message_handler(message: Message) -> None:

    await safe_delete_message(message)

    warning_message = await message.answer(
        "Пока здесь лучше пользоваться кнопками меню 🐾"
    )

    await asyncio.sleep(3)
    await safe_delete_message(warning_message)