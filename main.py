import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import commands, menu, quiz, result_actions, result_view, start


logging.basicConfig(level=logging.INFO)


async def set_bot_commands(bot: Bot) -> None:
    """Set visible Telegram bot commands."""

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть стартовый экран"),
            BotCommand(command="help", description="Справка по боту"),
            BotCommand(command="result", description="Показать последний результат"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
        ]
    )


async def main() -> None:
    """Start the Telegram bot."""

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(menu.router)
    dp.include_router(quiz.router)
    dp.include_router(result_actions.router)
    dp.include_router(result_view.router)

    await set_bot_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())