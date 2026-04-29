import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.handlers import commands, fallback, menu, quiz, result_actions, result_view, start
from bot.repositories.database import close_db_pool, init_db_pool
from bot.repositories.redis_client import close_redis_client, init_redis_client


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть стартовый экран"),
            BotCommand(command="help", description="Справка по боту"),
            BotCommand(command="result", description="Показать последний результат"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
        ]
    )


async def main() -> None:
    logger.info("Starting PythonZoo bot")

    await init_db_pool()
    redis_client = await init_redis_client()

    bot = Bot(token=settings.bot_token)
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(menu.router)
    dp.include_router(quiz.router)
    dp.include_router(result_actions.router)
    dp.include_router(result_view.router)
    dp.include_router(fallback.router)

    logger.info("Routers registered")

    await set_bot_commands(bot)
    logger.info("Bot commands registered")

    try:
        logger.info("Starting polling")
        await dp.start_polling(bot)
    finally:
        logger.info("Stopping PythonZoo bot")

        await close_db_pool()
        await close_redis_client()
        await bot.session.close()

        logger.info("PythonZoo bot stopped")


if __name__ == "__main__":
    asyncio.run(main())