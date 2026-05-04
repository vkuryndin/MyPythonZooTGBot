import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from bot.config import settings
from bot.handlers import (
    admin,
    cancel_actions,
    commands,
    contact_actions,
    error_handler,
    fallback,
    feedback_actions,
    menu,
    quiz,
    result_image_actions,
    result_view,
    share_actions,
    start,
)
from bot.repositories.database import close_db_pool, init_db_pool
from bot.repositories.redis_client import close_redis_client, init_redis_client
from bot.services.admin_notification_service import (
    notify_admin_about_critical_startup_error,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    user_commands = [
        BotCommand(command="start", description="Открыть стартовый экран"),
        BotCommand(command="help", description="Справка по боту"),
        BotCommand(command="result", description="Показать последний результат"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ]

    await bot.set_my_commands(
        commands=user_commands,
        scope=BotCommandScopeDefault(),
    )

    if settings.admin_chat_id <= 0:
        logger.warning("ADMIN_CHAT_ID is not configured, admin commands are hidden")
        return

    admin_commands = [
        *user_commands,
        BotCommand(command="admin", description="Админский режим"),
        BotCommand(command="admin_stats", description="Статистика проекта"),
        BotCommand(command="admin_contacts", description="Последние обращения"),
        BotCommand(command="admin_feedback", description="Последние отзывы"),
    ]

    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeChat(chat_id=settings.admin_chat_id),
    )


def register_routers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(admin.router)
    dp.include_router(menu.router)
    dp.include_router(quiz.router)
    dp.include_router(share_actions.router)
    dp.include_router(contact_actions.router)
    dp.include_router(feedback_actions.router)
    dp.include_router(cancel_actions.router)
    dp.include_router(result_image_actions.router)
    dp.include_router(result_view.router)
    dp.include_router(error_handler.router)
    # Fallback must stay last: it catches only messages not handled elsewhere.
    dp.include_router(fallback.router)


async def main() -> int:
    logger.info("Starting MoscowZoo bot")

    # Create the bot before service initialization so startup failures
    # can still be reported to the admin.
    bot = Bot(token=settings.bot_token)
    startup_stage = "initialization"

    try:
        # Track startup stage to make admin alerts useful without exposing secrets.
        startup_stage = "PostgreSQL initialization"
        await init_db_pool()

        startup_stage = "Redis initialization"
        redis_client = await init_redis_client()

        startup_stage = "Dispatcher initialization"
        storage = RedisStorage(redis=redis_client)
        dp = Dispatcher(storage=storage)

        register_routers(dp)
        logger.info("Routers registered")

        startup_stage = "Bot commands registration"
        await set_bot_commands(bot)
        logger.info("Bot commands registered")

        startup_stage = "Polling"
        logger.info("Starting polling")
        await dp.start_polling(bot)

        return 0

    except Exception as error:
        logger.exception(
            "MoscowZoo bot startup failed stage=%s error_type=%s",
            startup_stage,
            type(error).__name__,
        )

        await notify_admin_about_critical_startup_error(
            bot=bot,
            stage=startup_stage,
            error=error,
        )

        return 1

    finally:
        logger.info("Stopping MoscowZoo bot")

        await close_db_pool()
        await close_redis_client()
        await bot.session.close()

        logger.info("MoscowZoo bot stopped")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))