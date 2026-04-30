from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.menu import show_main_menu
from bot.handlers.quiz import cancel_active_quiz, is_quiz_active
from bot.handlers.result_view import show_last_result
from bot.services.action_names import build_cancel_text, get_cancelled_action_name
from bot.services.message_utils import safe_delete_messages_by_ids
from bot.services.result_service import has_last_result


router = Router()


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
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
        "После результата можно поделиться им, оставить отзыв, связаться с сотрудником и сгенерировать ИИ-картинку с вашим тотемным животным."
    )


@router.message(Command("result"))
async def result_handler(message: Message) -> None:
    await show_last_result(
        message=message,
        user_id=message.from_user.id,
    )


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id

    current_state = await state.get_state()
    quiz_active = await is_quiz_active(user_id)

    action_name = get_cancelled_action_name(
        current_state=current_state,
        quiz_active=quiz_active,
    )

    if action_name is None:
        await message.answer(
            "Активного действия для отмены не было.\n\n"
            "Используй кнопки меню или команду /help, если нужна подсказка 🐾"
        )
        return

    await state.clear()

    quiz_message_ids = await cancel_active_quiz(user_id)
    await safe_delete_messages_by_ids(message, quiz_message_ids)

    cancel_text = build_cancel_text(action_name)

    if await has_last_result(user_id):
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