import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import menu, quiz, result_actions, start


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Start the Telegram bot."""

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(quiz.router)
    dp.include_router(result_actions.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())