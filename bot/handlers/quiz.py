import asyncio
import random
from typing import Any

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
    add_image_tags,
    add_quiz_message_id,
    add_scores,
    create_quiz_session,
    delete_quiz_session,
    get_quiz_session,
    is_quiz_session_active,
    set_question_position,
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
        """Check whether message author has an active quiz."""

        if message.from_user is None:
            return False

        return await is_quiz_session_active(message.from_user.id)


@router.callback_query(lambda callback: callback.data == "start_quiz")
async def start_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start quiz from the first shuffled question."""

    await state.clear()
    await safe_delete_callback_message(callback)

    user_id = callback.from_user.id

    old_message_ids = await delete_quiz_session(user_id)
    await safe_delete_messages_by_ids(callback.message, old_message_ids)

    question_order, option_orders = build_quiz_order()

    await create_quiz_session(
        user_id=user_id,
        question_order=question_order,
        option_orders=option_orders,
    )

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

    if not is_new_quiz_session_format(session):
        await delete_quiz_session(user_id)
        await remove_old_buttons(callback)
        await callback.answer("Викторина обновилась. Запусти её заново 🙂")
        return

    _, question_position_text, displayed_option_index_text = callback.data.split(":")
    question_position = int(question_position_text)
    displayed_option_index = int(displayed_option_index_text)

    current_question_position = int(session["question_position"])

    if question_position != current_question_position:
        await remove_old_buttons(callback)
        await callback.answer("Этот вопрос уже неактуален 🙂")
        return

    original_question_index = get_original_question_index(
        session=session,
        question_position=question_position,
    )

    option_order = get_option_order(
        session=session,
        original_question_index=original_question_index,
    )

    original_option_index = option_order[displayed_option_index]

    await mark_answer_selected(
        callback=callback,
        session=session,
        question_position=question_position,
        displayed_option_index=displayed_option_index,
        original_question_index=original_question_index,
        option_order=option_order,
    )

    option_scores = quiz_service.get_option_scores(
        original_question_index,
        original_option_index,
    )
    scores = await add_scores(user_id, option_scores)

    option_image_tags = quiz_service.get_option_image_tags(
        original_question_index,
        original_option_index,
    )
    await add_image_tags(user_id, option_image_tags)

    if is_last_question_position(session, question_position):
        await send_result(callback, user_id, scores)
    else:
        await set_question_position(user_id, question_position + 1)
        await send_question(callback, user_id)

    await callback.answer("Ответ принят!")


async def send_question(callback: CallbackQuery, user_id: int) -> None:
    """Send current shuffled quiz question to user."""

    session = await get_quiz_session(user_id)

    if session is None:
        await callback.message.answer(
            "Викторина не найдена. Нажми «🐾 Начать викторину»."
        )
        return

    if not is_new_quiz_session_format(session):
        await delete_quiz_session(user_id)
        await callback.message.answer(
            "Викторина обновилась. Нажми «🐾 Начать викторину» ещё раз."
        )
        return

    question_position = int(session["question_position"])

    original_question_index = get_original_question_index(
        session=session,
        question_position=question_position,
    )

    option_order = get_option_order(
        session=session,
        original_question_index=original_question_index,
    )

    question = build_display_question(
        original_question_index=original_question_index,
        option_order=option_order,
    )

    total_questions = len(session["question_order"])

    options_text = "\n".join(
        f"{option_index + 1}. {option['text']}"
        for option_index, option in enumerate(question["options"])
    )

    sent_message = await callback.message.answer(
        f"Вопрос {question_position + 1} из {total_questions}\n\n"
        f"{question['text']}\n\n"
        f"{options_text}\n\n"
        "Выбери номер ответа 👇",
        reply_markup=get_question_keyboard(question, question_position),
    )

    await add_quiz_message_id(user_id, sent_message.message_id)


async def mark_answer_selected(
    callback: CallbackQuery,
    session: dict[str, Any],
    question_position: int,
    displayed_option_index: int,
    original_question_index: int,
    option_order: list[int],
) -> None:
    """Remove old buttons and show selected answer in the old question message."""

    question = build_display_question(
        original_question_index=original_question_index,
        option_order=option_order,
    )

    total_questions = len(session["question_order"])

    options_text = "\n".join(
        f"{index + 1}. {option['text']}"
        for index, option in enumerate(question["options"])
    )

    selected_option_text = question["options"][displayed_option_index]["text"]

    text = (
        f"Вопрос {question_position + 1} из {total_questions}\n\n"
        f"{question['text']}\n\n"
        f"{options_text}\n\n"
        f"✅ Твой ответ: {displayed_option_index + 1}. {selected_option_text}"
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

    session = await get_quiz_session(user_id)
    image_tags = session.get("image_tags", []) if session else []

    animal = quiz_service.get_result_animal(scores)

    await save_quiz_result(
        user=callback.from_user,
        animal=animal,
        scores=scores,
        image_tags=image_tags,
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


def build_quiz_order() -> tuple[list[int], dict[str, list[int]]]:
    """Build shuffled question order and shuffled option order for each question."""

    total_questions = quiz_service.get_total_questions_count()

    question_order = list(range(total_questions))
    random.shuffle(question_order)

    option_orders = {}

    for original_question_index in question_order:
        question = quiz_service.get_question(original_question_index)
        option_order = list(range(len(question["options"])))
        random.shuffle(option_order)

        option_orders[str(original_question_index)] = option_order

    return question_order, option_orders


def build_display_question(
    original_question_index: int,
    option_order: list[int],
) -> dict[str, Any]:
    """Build question object with options ordered for current user session."""

    original_question = quiz_service.get_question(original_question_index)

    return {
        **original_question,
        "options": [
            original_question["options"][original_option_index]
            for original_option_index in option_order
        ],
    }


def is_new_quiz_session_format(session: dict[str, Any]) -> bool:
    """Check whether Redis quiz session contains shuffled order fields."""

    return (
        "question_position" in session
        and "question_order" in session
        and "option_orders" in session
    )


def get_original_question_index(
    session: dict[str, Any],
    question_position: int,
) -> int:
    """Get original question index from shuffled session position."""

    return int(session["question_order"][question_position])


def get_option_order(
    session: dict[str, Any],
    original_question_index: int,
) -> list[int]:
    """Get shuffled option order for original question index."""

    return [
        int(option_index)
        for option_index in session["option_orders"][str(original_question_index)]
    ]


def is_last_question_position(
    session: dict[str, Any],
    question_position: int,
) -> bool:
    """Check whether current shuffled question position is the last one."""

    return question_position + 1 >= len(session["question_order"])