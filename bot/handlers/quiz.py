from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from bot.handlers.menu import show_main_menu

from bot.handlers.result_view import send_animal_result, show_last_result
from bot.services.session_storage import get_last_result, save_last_result

from bot.keyboards.quiz_keyboards import get_question_keyboard
from bot.services.message_utils import (
    safe_delete_callback_message,
    safe_delete_message,
    safe_remove_keyboard,
)
from bot.services.quiz_service import quiz_service


import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message


router = Router()

user_quiz_state: dict[int, dict] = {}


@router.callback_query(lambda callback: callback.data == "start_quiz")
async def start_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start quiz from the first question."""

    await state.clear()
    await safe_delete_callback_message(callback)

    user_id = callback.from_user.id
    user_quiz_state[user_id] = {
        "question_index": 0,
        "scores": {},
    }

    await send_question(callback, user_id)
    await callback.answer()


@router.callback_query(lambda callback: callback.data == "cancel_quiz")
async def cancel_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current quiz and return to result screen or main menu."""

    await state.clear()

    user_id = callback.from_user.id
    user_quiz_state.pop(user_id, None)

    await safe_delete_callback_message(callback)

    if get_last_result(user_id) is not None:
        await show_last_result(
            message=callback.message,
            user_id=user_id,
            prefix_text="Викторина остановлена. Возвращаю к твоему последнему результату 🐾",
        )
    else:
        await show_main_menu(
            message=callback.message,
            user_id=user_id,
            text="Викторина остановлена. Возвращаю в главное меню 🐾",
        )

    await callback.answer()

@router.message(lambda message: message.from_user.id in user_quiz_state, F.text)
async def quiz_text_message_handler(message: Message) -> None:
    """Delete text messages while quiz is active."""

    await safe_delete_message(message)

    warning_message = await message.answer(
        "Во время викторины выбери один из вариантов ответа кнопкой 👇"
    )

    await asyncio.sleep(3)
    await safe_delete_message(warning_message)

@router.message(lambda message: message.from_user.id in user_quiz_state, F.text)
async def quiz_text_message_handler(message: Message) -> None:
    """Handle text messages while quiz is active."""

    await message.answer(
        "Во время викторины выбери один из вариантов ответа кнопкой 👇"
    )

@router.callback_query(lambda callback: callback.data.startswith("quiz_answer:"))
async def quiz_answer_handler(callback: CallbackQuery) -> None:
    """Handle selected quiz answer and show next question or result."""

    user_id = callback.from_user.id

    if user_id not in user_quiz_state:
        await remove_old_buttons(callback)
        await callback.answer("Эта викторина уже завершена или не начата 🙂")
        return

    _, question_index_text, option_index_text = callback.data.split(":")
    question_index = int(question_index_text)
    option_index = int(option_index_text)

    state = user_quiz_state[user_id]
    current_question_index = state["question_index"]

    if question_index != current_question_index:
        await remove_old_buttons(callback)
        await callback.answer("Этот вопрос уже неактуален 🙂")
        return

    await mark_answer_selected(callback, question_index, option_index)

    scores = state["scores"]
    option_scores = quiz_service.get_option_scores(question_index, option_index)

    for animal_id, points in option_scores.items():
        scores[animal_id] = scores.get(animal_id, 0) + points

    if quiz_service.is_last_question(question_index):
        await send_result(callback, user_id)
        user_quiz_state.pop(user_id, None)
    else:
        state["question_index"] = question_index + 1
        await send_question(callback, user_id)

    await callback.answer("Ответ принят!")


async def send_question(callback: CallbackQuery, user_id: int) -> None:
    """Send current quiz question to user."""

    state = user_quiz_state[user_id]
    question_index = state["question_index"]
    question = quiz_service.get_question(question_index)

    total_questions = quiz_service.get_total_questions_count()

    options_text = "\n".join(
        f"{option_index + 1}. {option['text']}"
        for option_index, option in enumerate(question["options"])
    )

    await callback.message.answer(
        f"Вопрос {question_index + 1} из {total_questions}\n\n"
        f"{question['text']}\n\n"
        f"{options_text}\n\n"
        "Выбери номер ответа 👇",
        reply_markup=get_question_keyboard(question, question_index),
    )


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


async def send_result(callback: CallbackQuery, user_id: int) -> None:
    """Send quiz result to user."""

    scores = user_quiz_state[user_id]["scores"]
    animal = quiz_service.get_result_animal(scores)

    save_last_result(user_id, animal)

    await send_animal_result(callback.message, animal)

def cancel_active_quiz(user_id: int) -> None:
    """Cancel active quiz for user."""

    user_quiz_state.pop(user_id, None)