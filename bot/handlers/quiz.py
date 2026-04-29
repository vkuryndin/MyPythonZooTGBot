import asyncio
import random
import uuid
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

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
from bot.repositories.redis_client import get_redis_client
from bot.services.message_utils import (
    safe_delete_callback_message,
    safe_delete_message,
    safe_delete_messages_by_ids,
    safe_remove_keyboard,
)
from bot.services.quiz_service import quiz_service
from bot.services.result_service import has_last_result


router = Router()

QUIZ_ANSWER_LOCK_TTL_SECONDS = 10


class ActiveQuizFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False

        return await is_quiz_session_active(message.from_user.id)


def get_callback_message(callback: CallbackQuery) -> Message | None:
    if isinstance(callback.message, Message):
        return callback.message

    return None


def _quiz_answer_lock_key(user_id: int) -> str:
    return f"python_zoo:quiz_answer_lock:{user_id}"


async def acquire_quiz_answer_lock(user_id: int) -> str | None:
    redis_client = get_redis_client()
    token = uuid.uuid4().hex

    acquired = await redis_client.set(
        _quiz_answer_lock_key(user_id),
        token,
        ex=QUIZ_ANSWER_LOCK_TTL_SECONDS,
        nx=True,
    )

    if acquired:
        return token

    return None


async def release_quiz_answer_lock(user_id: int, token: str) -> None:
    redis_client = get_redis_client()

    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    await redis_client.eval(
        script,
        1,
        _quiz_answer_lock_key(user_id),
        token,
    )


def parse_quiz_answer_callback(callback_data: str | None) -> tuple[int, int] | None:
    if callback_data is None:
        return None

    parts = callback_data.split(":")

    if len(parts) != 3 or parts[0] != "quiz_answer":
        return None

    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


@router.callback_query(lambda callback: callback.data == "start_quiz")
async def start_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await state.clear()
    await safe_delete_callback_message(callback)

    user_id = callback.from_user.id

    old_message_ids = await delete_quiz_session(user_id)
    await safe_delete_messages_by_ids(message, old_message_ids)

    question_order, option_orders = build_quiz_order()

    await create_quiz_session(
        user_id=user_id,
        question_order=question_order,
        option_orders=option_orders,
    )

    await send_question(message, user_id)
    await callback.answer()


@router.callback_query(lambda callback: callback.data == "cancel_quiz")
async def cancel_quiz_handler(callback: CallbackQuery, state: FSMContext) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await state.clear()

    user_id = callback.from_user.id
    quiz_message_ids = await delete_quiz_session(user_id)

    await safe_delete_messages_by_ids(message, quiz_message_ids)

    if await has_last_result(user_id):
        await message.answer(
            "Викторина остановлена. Возвращаю к твоему последнему результату 🐾"
        )

        await show_last_result(
            message=message,
            user_id=user_id,
        )
    else:
        await show_main_menu(
            message=message,
            user_id=user_id,
            text="Викторина остановлена. Возвращаю в главное меню 🐾",
        )

    await callback.answer()


@router.message(ActiveQuizFilter(), F.text)
async def quiz_text_message_handler(message: Message) -> None:
    await safe_delete_message(message)

    warning_message = await message.answer(
        "Во время викторины выбери один из вариантов ответа кнопкой 👇"
    )

    await asyncio.sleep(3)
    await safe_delete_message(warning_message)


@router.callback_query(
    lambda callback: bool(callback.data and callback.data.startswith("quiz_answer:"))
)
async def quiz_answer_handler(callback: CallbackQuery) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    user_id = callback.from_user.id
    lock_token = await acquire_quiz_answer_lock(user_id)

    if lock_token is None:
        await callback.answer("Ответ уже обрабатывается 🙂")
        return

    try:
        await process_quiz_answer(callback, message, user_id)
    finally:
        await release_quiz_answer_lock(user_id, lock_token)


async def process_quiz_answer(
    callback: CallbackQuery,
    message: Message,
    user_id: int,
) -> None:
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

    parsed_callback = parse_quiz_answer_callback(callback.data)

    if parsed_callback is None:
        await remove_old_buttons(callback)
        await callback.answer("Некорректный ответ. Запусти викторину заново 🙂")
        return

    question_position, displayed_option_index = parsed_callback

    try:
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

        if displayed_option_index < 0 or displayed_option_index >= len(option_order):
            await remove_old_buttons(callback)
            await callback.answer("Некорректный вариант ответа 🙂")
            return

        original_option_index = option_order[displayed_option_index]

        await mark_answer_selected(
            callback=callback,
            message=message,
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
            await send_result(
                message=message,
                user=callback.from_user,
                scores=scores,
            )
        else:
            await set_question_position(user_id, question_position + 1)
            await send_question(message, user_id)

        await callback.answer("Ответ принят!")

    except (KeyError, IndexError, TypeError, ValueError):
        await delete_quiz_session(user_id)
        await remove_old_buttons(callback)
        await callback.answer("Сессия викторины повреждена. Запусти её заново 🙂")


async def send_question(message: Message, user_id: int) -> None:
    session = await get_quiz_session(user_id)

    if session is None:
        await message.answer(
            "Викторина не найдена. Нажми «🐾 Начать викторину»."
        )
        return

    if not is_new_quiz_session_format(session):
        await delete_quiz_session(user_id)
        await message.answer(
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

    sent_message = await message.answer(
        f"Вопрос {question_position + 1} из {total_questions}\n\n"
        f"{question['text']}\n\n"
        f"{options_text}\n\n"
        "Выбери номер ответа 👇",
        reply_markup=get_question_keyboard(question, question_position),
    )

    await add_quiz_message_id(user_id, sent_message.message_id)


async def mark_answer_selected(
    callback: CallbackQuery,
    message: Message,
    session: dict[str, Any],
    question_position: int,
    displayed_option_index: int,
    original_question_index: int,
    option_order: list[int],
) -> None:
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
        await message.edit_text(
            text=text,
            reply_markup=None,
        )
    except TelegramBadRequest:
        await remove_old_buttons(callback)


async def remove_old_buttons(callback: CallbackQuery) -> None:
    await safe_remove_keyboard(callback)


async def send_result(
    message: Message,
    user: User,
    scores: dict[str, int],
) -> None:
    user_id = user.id
    session = await get_quiz_session(user_id)
    image_tags = session.get("image_tags", []) if session else []

    if not scores:
        await delete_quiz_session(user_id)
        await message.answer(
            "Не удалось посчитать результат. Попробуй пройти викторину ещё раз 🐾"
        )
        return

    animal = quiz_service.get_result_animal(scores)

    await save_quiz_result(
        user=user,
        animal=animal,
        scores=scores,
        image_tags=image_tags,
    )

    quiz_message_ids = await delete_quiz_session(user_id)
    await safe_delete_messages_by_ids(message, quiz_message_ids)

    await send_animal_result(message, animal)


async def cancel_active_quiz(user_id: int) -> list[int]:
    return await delete_quiz_session(user_id)


async def is_quiz_active(user_id: int) -> bool:
    return await is_quiz_session_active(user_id)


def build_quiz_order() -> tuple[list[int], dict[str, list[int]]]:
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
    original_question = quiz_service.get_question(original_question_index)

    return {
        **original_question,
        "options": [
            original_question["options"][original_option_index]
            for original_option_index in option_order
        ],
    }


def is_new_quiz_session_format(session: dict[str, Any]) -> bool:
    return (
        isinstance(session.get("question_position"), int)
        and isinstance(session.get("question_order"), list)
        and isinstance(session.get("option_orders"), dict)
    )


def get_original_question_index(
    session: dict[str, Any],
    question_position: int,
) -> int:
    return int(session["question_order"][question_position])


def get_option_order(
    session: dict[str, Any],
    original_question_index: int,
) -> list[int]:
    return [
        int(option_index)
        for option_index in session["option_orders"][str(original_question_index)]
    ]


def is_last_question_position(
    session: dict[str, Any],
    question_position: int,
) -> bool:
    return question_position + 1 >= len(session["question_order"])