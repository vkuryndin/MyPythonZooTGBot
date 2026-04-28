from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.main_menu import get_main_menu_keyboard


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Handle the /start command."""

    await message.answer(
        "Привет! 🐾\n\n"
        "Я бот Московского зоопарка. Помогу узнать, "
        "какое животное могло бы стать твоим тотемным.\n\n"
        "Ответь на несколько вопросов, а в конце я покажу результат "
        "и расскажу, как можно поддержать животных через программу опеки.",
        reply_markup=get_main_menu_keyboard(),
    )