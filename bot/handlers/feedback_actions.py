import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User
from asyncpg.exceptions import PostgresError

from bot.config import settings
from bot.handlers.result_view import show_last_result
from bot.keyboards.action_keyboards import (
    get_feedback_comment_keyboard,
    get_feedback_rating_keyboard,
    get_feedback_reply_contact_keyboard,
    get_feedback_reply_method_keyboard,
)
from bot.repositories.feedback_repository import save_feedback
from bot.services.email_service import send_contact_email
from bot.services.message_utils import (
    safe_delete_callback_message,
    safe_delete_message,
    safe_delete_message_by_id,
)
from bot.services.rate_limit_service import check_user_cooldown
from bot.services.result_service import get_last_result_animal
from bot.services.user_input_service import (
    MAX_REPLY_CONTACT_LENGTH,
    MAX_STAFF_MESSAGE_LENGTH,
    MAX_USER_TEXT_LENGTH,
    get_callback_message,
    is_valid_email,
    is_valid_telegram_username,
    limit_text,
)
from bot.states.user_states import FeedbackState


router = Router()
logger = logging.getLogger(__name__)

FEEDBACK_COOLDOWN_SECONDS = 300

FEEDBACK_STEPS = [
    ("questions_quality", "качество и понятность вопросов"),
    ("answers_quality", "качество и оригинальность ответов"),
    ("images_quality", "качество картинок"),
    ("navigation_quality", "понятность бота, меню и общей навигации"),
    ("overall_quality", "викторину в целом"),
]


@router.callback_query(lambda callback: callback.data == "leave_feedback")
async def leave_feedback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    animal = await get_last_result_animal(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    await safe_delete_callback_message(callback)

    await state.update_data(
        result_animal=animal["name"],
        feedback_step=0,
        feedback_ratings={},
    )
    await state.set_state(FeedbackState.waiting_for_rating)

    await send_feedback_rating_question(message, state)
    await callback.answer()


async def send_feedback_rating_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    step_index = int(data.get("feedback_step", 0))

    _, question_text = FEEDBACK_STEPS[step_index]

    sent_message = await message.answer(
        f"Оценка {step_index + 1} из {len(FEEDBACK_STEPS)} ⭐\n\n"
        f"Оцени {question_text} от 1 до 5.\n\n"
        "1 — совсем плохо\n"
        "5 — отлично",
        reply_markup=get_feedback_rating_keyboard(),
    )

    await state.update_data(
        feedback_rating_prompt_message_id=sent_message.message_id,
    )


@router.callback_query(
    FeedbackState.waiting_for_rating,
    F.data.startswith("feedback_rating:"),
)
async def feedback_rating_handler(callback: CallbackQuery, state: FSMContext) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    rating = int((callback.data or "").split(":")[1])

    data = await state.get_data()
    step_index = int(data.get("feedback_step", 0))
    ratings = data.get("feedback_ratings", {})

    rating_key, _ = FEEDBACK_STEPS[step_index]
    ratings[rating_key] = rating

    next_step_index = step_index + 1

    if next_step_index < len(FEEDBACK_STEPS):
        await state.update_data(
            feedback_step=next_step_index,
            feedback_ratings=ratings,
        )
        await send_feedback_rating_question(message, state)
    else:
        sent_message = await message.answer(
            "Спасибо! Все оценки получены ⭐\n\n"
            "Теперь можешь оставить короткий комментарий: "
            "что понравилось, что улучшить или какого животного не хватило.",
            reply_markup=get_feedback_comment_keyboard(),
        )

        await state.update_data(
            feedback_ratings=ratings,
            feedback_comment_prompt_message_id=sent_message.message_id,
        )
        await state.set_state(FeedbackState.waiting_for_comment)

    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_for_comment,
    F.data == "feedback_change_rating",
)
async def feedback_change_rating_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    data = await state.get_data()
    result_animal = data.get("result_animal", "не указан")

    await state.update_data(
        result_animal=result_animal,
        feedback_step=0,
        feedback_ratings={},
    )
    await state.set_state(FeedbackState.waiting_for_rating)

    await send_feedback_rating_question(message, state)
    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_for_comment,
    F.data == "skip_feedback_comment",
)
async def skip_feedback_comment_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    await state.update_data(feedback_comment=None)
    await state.set_state(FeedbackState.waiting_for_reply_method)

    await message.answer(
        "Спасибо! Комментарий пропущен.\n\n"
        "Хочешь, чтобы сотрудник зоопарка мог ответить тебе по отзыву?",
        reply_markup=get_feedback_reply_method_keyboard(),
    )
    await callback.answer()


@router.message(FeedbackState.waiting_for_comment, F.text)
async def feedback_comment_handler(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    data = await state.get_data()
    prompt_message_id = data.get("feedback_comment_prompt_message_id")

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)

    await state.update_data(
        feedback_comment=limit_text(message.text, MAX_USER_TEXT_LENGTH)
    )
    await state.set_state(FeedbackState.waiting_for_reply_method)

    await message.answer(
        "Спасибо, комментарий принят 🐾\n\n"
        "Хочешь, чтобы сотрудник зоопарка мог ответить тебе по отзыву?",
        reply_markup=get_feedback_reply_method_keyboard(),
    )


@router.callback_query(
    FeedbackState.waiting_for_reply_method,
    F.data.startswith("feedback_reply_method:"),
)
async def feedback_reply_method_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    reply_method = (callback.data or "").split(":")[1]

    if reply_method == "none":
        await finish_feedback_flow(
            message=message,
            user=callback.from_user,
            state=state,
            reply_method="none",
            reply_contact=None,
        )
        await callback.answer()
        return

    await state.update_data(reply_method=reply_method)
    await state.set_state(FeedbackState.waiting_for_reply_contact)

    if reply_method == "email":
        text = (
            "Введи email, на который сотрудник сможет ответить.\n\n"
            "Например: name@example.com\n\n"
            "Мы не сохраняем этот email в базе. "
            "Он будет использован только для ответа на твой отзыв."
        )
    else:
        text = (
            "Введи Telegram-ник, на который сотрудник сможет ответить.\n\n"
            "Например: @username\n\n"
            "Мы не сохраняем этот Telegram-ник в базе. "
            "Он будет использован только для ответа на твой отзыв."
        )

    sent_message = await message.answer(
        text,
        reply_markup=get_feedback_reply_contact_keyboard(),
    )

    await state.update_data(
        feedback_reply_contact_prompt_message_id=sent_message.message_id,
    )
    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_for_reply_contact,
    F.data == "feedback_back_to_reply_method",
)
async def feedback_back_to_reply_method_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    await state.set_state(FeedbackState.waiting_for_reply_method)

    await message.answer(
        "Хочешь, чтобы сотрудник зоопарка мог ответить тебе по отзыву?",
        reply_markup=get_feedback_reply_method_keyboard(),
    )
    await callback.answer()


@router.message(FeedbackState.waiting_for_reply_contact, F.text)
async def feedback_reply_contact_handler(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    data = await state.get_data()
    reply_method = data.get("reply_method", "none")
    prompt_message_id = data.get("feedback_reply_contact_prompt_message_id")

    reply_contact = limit_text(message.text, MAX_REPLY_CONTACT_LENGTH)

    if reply_method == "email" and not is_valid_email(reply_contact):
        await safe_delete_message(message)

        await message.answer(
            "Почта выглядит некорректно. Введи email в формате name@example.com.\n\n"
            "Мы не сохраняем этот email в базе. "
            "Он будет использован только для ответа на твой отзыв.",
            reply_markup=get_feedback_reply_contact_keyboard(),
        )
        return

    if reply_method == "telegram":
        if not is_valid_telegram_username(reply_contact):
            await safe_delete_message(message)

            await message.answer(
                "Telegram-ник выглядит некорректно. Введи ник в формате @username.",
                reply_markup=get_feedback_reply_contact_keyboard(),
            )
            return

        if not reply_contact.startswith("@"):
            reply_contact = f"@{reply_contact}"

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)

    await finish_feedback_flow(
        message=message,
        user=message.from_user,
        state=state,
        reply_method=reply_method,
        reply_contact=reply_contact,
    )


def build_feedback_staff_message(
    user: User,
    result_animal: str,
    ratings: dict,
    comment: str,
    reply_method: str,
    reply_contact: str | None,
) -> str:
    username = f"@{user.username}" if user.username else "не указан"

    if reply_method == "email":
        reply_text = f"Пользователь просит ответить на почту: {reply_contact}"
    elif reply_method == "telegram":
        reply_text = f"Пользователь просит ответить в Telegram: {reply_contact}"
    else:
        reply_text = "Ответ пользователю не требуется."

    text = (
        "⭐ Новый отзыв о викторине PythonZoo\n\n"
        f"Пользователь: {limit_text(user.full_name, 120)}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user.id}\n"
        f"Результат викторины: {result_animal}\n\n"
        "Оценки:\n"
        f"1. Качество и понятность вопросов: "
        f"{ratings.get('questions_quality', 'не указано')} из 5\n"
        f"2. Качество и оригинальность ответов: "
        f"{ratings.get('answers_quality', 'не указано')} из 5\n"
        f"3. Качество картинок: "
        f"{ratings.get('images_quality', 'не указано')} из 5\n"
        f"4. Понятность бота, меню и навигации: "
        f"{ratings.get('navigation_quality', 'не указано')} из 5\n"
        f"5. Викторина в целом: "
        f"{ratings.get('overall_quality', 'не указано')} из 5\n\n"
        f"Комментарий:\n{comment}\n\n"
        f"Контакт для ответа:\n{reply_text}"
    )

    return limit_text(text, MAX_STAFF_MESSAGE_LENGTH)


async def send_feedback_to_staff(
    bot: Bot,
    subject: str,
    body: str,
) -> tuple[str, bool, bool]:
    telegram_sent = False
    email_sent = False

    if settings.admin_chat_id > 0:
        try:
            await bot.send_message(
                chat_id=settings.admin_chat_id,
                text=body,
                parse_mode=None,
            )
            telegram_sent = True
        except TelegramAPIError:
            telegram_sent = False

    try:
        await send_contact_email(
            subject=subject,
            body=body,
        )
        email_sent = True
    except Exception:
        email_sent = False

    if telegram_sent and email_sent:
        return (
            "Спасибо за подробный отзыв! 🐾\n\n"
            "Мы отправили его сотруднику в Telegram и на почту.",
            telegram_sent,
            email_sent,
        )

    if telegram_sent and not email_sent:
        return (
            "Спасибо за отзыв! 🐾\n\n"
            "Отзыв отправлен в Telegram. На почту отправить не удалось — "
            "проверь настройки SMTP в .env.",
            telegram_sent,
            email_sent,
        )

    if email_sent and not telegram_sent:
        return (
            "Спасибо за отзыв! 🐾\n\n"
            "Отзыв отправлен на почту. В Telegram отправить не удалось — "
            "проверь ADMIN_CHAT_ID.",
            telegram_sent,
            email_sent,
        )

    return (
        "Спасибо за отзыв! 🐾\n\n"
        "Сейчас не удалось отправить его сотруднику. "
        "Проверь ADMIN_CHAT_ID и SMTP-настройки в .env.",
        telegram_sent,
        email_sent,
    )


async def finish_feedback_flow(
    message: Message,
    user: User,
    state: FSMContext,
    reply_method: str,
    reply_contact: str | None,
) -> None:
    allowed, retry_after = await check_user_cooldown(
        user_id=user.id,
        action="feedback",
        seconds=FEEDBACK_COOLDOWN_SECONDS,
    )

    if not allowed:
        await state.clear()

        await message.answer(
            "Отзыв можно отправлять не чаще одного раза в 5 минут.\n"
            f"Попробуй ещё раз примерно через {retry_after} сек."
        )

        await show_last_result(message=message, user_id=user.id)
        return

    data = await state.get_data()
    ratings = data.get("feedback_ratings", {})
    result_animal = data.get("result_animal", "не указан")
    comment = data.get("feedback_comment")

    staff_comment = comment if comment else "Комментарий не оставлен."

    feedback_message = build_feedback_staff_message(
        user=user,
        result_animal=result_animal,
        ratings=ratings,
        comment=staff_comment,
        reply_method=reply_method,
        reply_contact=reply_contact,
    )

    delivery_text, telegram_sent, email_sent = await send_feedback_to_staff(
        bot=message.bot,
        subject="PythonZoo: новый отзыв о викторине",
        body=feedback_message,
    )

    try:
        await save_feedback(
            user=user,
            animal_name=result_animal,
            ratings=ratings,
            comment_text=comment,
            telegram_sent=telegram_sent,
            email_sent=email_sent,
        )
    except PostgresError:
        logger.exception("Failed to save feedback")

    await state.clear()

    await message.answer(delivery_text)

    await show_last_result(
        message=message,
        user_id=user.id,
    )