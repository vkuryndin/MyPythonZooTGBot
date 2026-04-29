import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.menu import show_main_menu
from bot.handlers.result_view import send_animal_result, show_last_result
from bot.keyboards.quiz_keyboards import get_question_keyboard
from bot.repositories.quiz_result_repository import save_quiz_result
from bot.repositories.quiz_session_repository import (
    add_quiz_message_id,
    add_scores,
    create_quiz_session,
    delete_quiz_session,
    get_quiz_session,
    is_quiz_session_active,
    set_question_index,
)
from bot.services.message_utils import (
    safe_delete_callback_message,
    safe_delete_message,
    safe_delete_messages_by_ids,
    safe_remove_keyboard,
)
from bot.services.quiz_service import quiz_service
from bot.services.result_service import has_last_result



router = Router()


class ActiveQuizFilter(BaseFilter):
    """Filter messages from users who have an active quiz session."""

    async def __call__(self, message: Message) -> bool:
        return await is_quiz_session_active(message.from_user.id)


@router.callback_query(lambda callback: callback.data == "start_quiz")
async def start_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start quiz from the first question."""

    await state.clear()
    await safe_delete_callback_message(callback)

    user_id = callback.from_user.id

    old_message_ids = await delete_quiz_session(user_id)
    await safe_delete_messages_by_ids(callback.message, old_message_ids)

    await create_quiz_session(user_id)
    await send_question(callback, user_id)

    await callback.answer()


@router.callback_query(lambda callback: callback.data == "cancel_quiz")
async def cancel_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current quiz and return to result screen or main menu."""

    await state.clear()

    user_id = callback.from_user.id
    quiz_message_ids = await delete_quiz_session(user_id)

    await safe_delete_messages_by_ids(callback.message, quiz_message_ids)

    if await has_last_result(user_id):
        await callback.message.answer(
            "Викторина остановлена. Возвращаю к твоему последнему результату 🐾"
        )

        await show_last_result(
            message=callback.message,
            user_id=user_id,
        )
    else:
        await show_main_menu(
            message=callback.message,
            user_id=user_id,
            text="Викторина остановлена. Возвращаю в главное меню 🐾",
        )

    await callback.answer()


@router.message(ActiveQuizFilter(), F.text)
async def quiz_text_message_handler(message: Message) -> None:
    """Delete text messages while quiz is active."""

    await safe_delete_message(message)

    warning_message = await message.answer(
        "Во время викторины выбери один из вариантов ответа кнопкой 👇"
    )

    await asyncio.sleep(3)
    await safe_delete_message(warning_message)


@router.callback_query(lambda callback: callback.data.startswith("quiz_answer:"))
async def quiz_answer_handler(callback: CallbackQuery) -> None:
    """Handle selected quiz answer and show next question or result."""

    user_id = callback.from_user.id
    session = await get_quiz_session(user_id)

    if session is None:
        await remove_old_buttons(callback)
        await callback.answer("Эта викторина уже завершена или не начата 🙂")
        return

    _, question_index_text, option_index_text = callback.data.split(":")
    question_index = int(question_index_text)
    option_index = int(option_index_text)

    current_question_index = int(session["question_index"])

    if question_index != current_question_index:
        await remove_old_buttons(callback)
        await callback.answer("Этот вопрос уже неактуален 🙂")
        return

    await mark_answer_selected(callback, question_index, option_index)

    option_scores = quiz_service.get_option_scores(question_index, option_index)
    scores = await add_scores(user_id, option_scores)

    if quiz_service.is_last_question(question_index):
        await send_result(callback, user_id, scores)
    else:
        await set_question_index(user_id, question_index + 1)
        await send_question(callback, user_id)

    await callback.answer("Ответ принят!")


async def send_question(callback: CallbackQuery, user_id: int) -> None:
    """Send current quiz question to user."""

    session = await get_quiz_session(user_id)

    if session is None:
        await callback.message.answer(
            "Викторина не найдена. Нажми «🐾 Начать викторину»."
        )
        return

    question_index = int(session["question_index"])
    question = quiz_service.get_question(question_index)

    total_questions = quiz_service.get_total_questions_count()

    options_text = "\n".join(
        f"{option_index + 1}. {option['text']}"
        for option_index, option in enumerate(question["options"])
    )

    sent_message = await callback.message.answer(
        f"Вопрос {question_index + 1} из {total_questions}\n\n"
        f"{question['text']}\n\n"
        f"{options_text}\n\n"
        "Выбери номер ответа 👇",
        reply_markup=get_question_keyboard(question, question_index),
    )

    await add_quiz_message_id(user_id, sent_message.message_id)


async def mark_answer_selected(
    callback: CallbackQuery,
    question_index: int,
    option_index: int,
) -> None:
    """Remove old buttons and show selected answer in the old question message."""

    question = quiz_service.get_question(question_index)
    total_questions = quiz_service.get_total_questions_count()

    options_text = "\n".join(
        f"{index + 1}. {option['text']}"
        for index, option in enumerate(question["options"])
    )

    selected_option_text = question["options"][option_index]["text"]

    text = (
        f"Вопрос {question_index + 1} из {total_questions}\n\n"
        f"{question['text']}\n\n"
        f"{options_text}\n\n"
        f"✅ Твой ответ: {option_index + 1}. {selected_option_text}"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=None,
        )
    except TelegramBadRequest:
        await remove_old_buttons(callback)


async def remove_old_buttons(callback: CallbackQuery) -> None:
    """Remove inline keyboard from an old message."""

    await safe_remove_keyboard(callback)


async def send_result(
    callback: CallbackQuery,
    user_id: int,
    scores: dict[str, int],
) -> None:
    """Send quiz result to user."""

    animal = quiz_service.get_result_animal(scores)


    await save_quiz_result(
        user=callback.from_user,
        animal=animal,
        scores=scores,
    )

    quiz_message_ids = await delete_quiz_session(user_id)
    await safe_delete_messages_by_ids(callback.message, quiz_message_ids)

    await send_animal_result(callback.message, animal)


async def cancel_active_quiz(user_id: int) -> list[int]:
    """Cancel active quiz for user and return quiz message ids."""

    return await delete_quiz_session(user_id)


async def is_quiz_active(user_id: int) -> bool:
    """Check whether user has an active quiz."""

    return await is_quiz_session_active(user_id)