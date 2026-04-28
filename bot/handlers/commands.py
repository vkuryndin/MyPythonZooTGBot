from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.menu import show_main_menu
from bot.handlers.result_view import show_last_result
from bot.services.session_storage import get_last_result
from bot.handlers.quiz import cancel_active_quiz


router = Router()


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Show bot help."""

    await message.answer(
        "Справка по боту 🐾\n\n"
        "Я помогу пройти викторину и узнать твоё тотемное животное "
        "из Московского зоопарка.\n\n"
        "Основные команды:\n"
        "/start — открыть стартовый экран\n"
        "/help — показать эту справку\n"
        "/result — показать последний результат викторины\n"
        "/cancel — отменить текущее действие\n\n"
        "Во время викторины выбирай ответы кнопками. "
        "После результата можно поделиться им, оставить отзыв или связаться с сотрудником."
    )


@router.message(Command("result"))
async def result_handler(message: Message) -> None:
    """Show last quiz result."""

    await show_last_result(
        message=message,
        user_id=message.from_user.id,
    )


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """Cancel current action and return to result or main menu."""

    await state.clear()

    cancel_active_quiz(message.from_user.id)

    if get_last_result(message.from_user.id) is not None:
        await show_last_result(
            message=message,
            user_id=message.from_user.id,
            prefix_text="Текущее действие отменено.",
        )
    else:
        await show_main_menu(
            message=message,
            user_id=message.from_user.id,
            text="Текущее действие отменено. Возвращаю в главное меню 🐾",
        )