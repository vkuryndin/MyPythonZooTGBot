from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.menu import show_main_menu
from bot.handlers.result_view import show_last_result
from bot.services.session_storage import get_last_result
from bot.handlers.quiz import cancel_active_quiz, is_quiz_active
from bot.services.action_names import build_cancel_text, get_cancelled_action_name
from bot.services.message_utils import safe_delete_messages_by_ids

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

    user_id = message.from_user.id

    current_state = await state.get_state()
    action_name = get_cancelled_action_name(
        current_state=current_state,
        quiz_active=is_quiz_active(user_id),
    )
    cancel_text = build_cancel_text(action_name)

    await state.clear()
    quiz_message_ids = cancel_active_quiz(user_id)
    await safe_delete_messages_by_ids(message, quiz_message_ids)

    if get_last_result(user_id) is not None:
        await message.answer(cancel_text)

        await show_last_result(
            message=message,
            user_id=user_id,
        )
    else:
        await show_main_menu(
            message=message,
            user_id=user_id,
            text=f"{cancel_text}\n\nВозвращаю в главное меню 🐾",
        )