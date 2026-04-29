from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.handlers.menu import show_start_screen


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Handle the /start command."""

    await show_start_screen(message)