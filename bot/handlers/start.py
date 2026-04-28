from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.handlers.menu import WELCOME_TEXT, show_main_menu


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Handle the /start command."""

    await show_main_menu(
        message=message,
        user_id=message.from_user.id,
        text=WELCOME_TEXT,
    )