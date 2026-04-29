import logging
import re
from urllib.parse import quote

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from bot.config import settings
from bot.handlers.menu import show_main_menu
from bot.handlers.result_view import show_last_result
from bot.keyboards.action_keyboards import (
    get_contact_cancel_keyboard,
    get_contact_method_keyboard,
    get_contact_reply_contact_keyboard,
    get_contact_reply_method_keyboard,
    get_feedback_comment_keyboard,
    get_feedback_rating_keyboard,
    get_feedback_reply_contact_keyboard,
    get_feedback_reply_method_keyboard,
    get_share_result_keyboard,
)
from bot.repositories.contact_repository import save_contact_request
from bot.repositories.feedback_repository import save_feedback
from bot.services.action_names import build_cancel_text, get_cancelled_action_name
from bot.services.email_service import send_contact_email
from bot.services.message_utils import (
    safe_delete_callback_message,
    safe_delete_message,
    safe_delete_message_by_id,
)
from bot.services.result_service import get_last_result_animal
from bot.states.user_states import ContactStaffState, FeedbackState


router = Router()
logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

FEEDBACK_STEPS = [
    ("questions_quality", "качество и понятность вопросов"),
    ("answers_quality", "качество и оригинальность ответов"),
    ("images_quality", "качество картинок"),
    ("navigation_quality", "понятность бота, меню и общей навигации"),
    ("overall_quality", "викторину в целом"),
]


def get_callback_message(callback: CallbackQuery) -> Message | None:
    """Return callback message only if it is accessible."""

    if isinstance(callback.message, Message):
        return callback.message

    return None


@router.callback_query(lambda callback: callback.data == "share_result")
async def share_result_handler(callback: CallbackQuery) -> None:
    """Show social share buttons for user's quiz result."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    animal = await get_last_result_animal(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    await safe_delete_callback_message(callback)

    share_text = (
        f"Моё тотемное животное в Московском зоопарке — {animal['name']}! 🐾\n\n"
        "Пройди викторину и узнай своё тотемное животное."
    )

    encoded_bot_link = quote(settings.bot_link)
    encoded_share_text = quote(share_text)
    encoded_full_text = quote(f"{share_text}\n\n{settings.bot_link}")

    telegram_share_url = (
        "https://t.me/share/url?"
        f"url={encoded_bot_link}&"
        f"text={encoded_share_text}"
    )
    vk_share_url = "https://vk.com/share.php?" f"url={encoded_bot_link}"
    whatsapp_share_url = "https://api.whatsapp.com/send?" f"text={encoded_full_text}"
    max_share_url = "https://max.ru/:share?" f"text={encoded_full_text}"

    keyboard = get_share_result_keyboard(
        telegram_share_url=telegram_share_url,
        vk_share_url=vk_share_url,
        whatsapp_share_url=whatsapp_share_url,
        max_share_url=max_share_url,
    )

    await message.answer(
        "Выбери, где хочешь поделиться результатом 👇",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(
    lambda callback: callback.data in {
        "contact_staff",
        "contact_staff:main",
        "contact_staff:result",
    }
)
async def contact_staff_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user to choose contact delivery method."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    animal = await get_last_result_animal(callback.from_user.id)

    if callback.data == "contact_staff:main":
        return_to_result = False
    elif callback.data == "contact_staff:result":
        return_to_result = True
    else:
        return_to_result = animal is not None

    await safe_delete_callback_message(callback)
    await state.clear()
    await state.update_data(return_to_result=return_to_result)

    await message.answer(
        "Как передать сообщение сотруднику зоопарка?",
        reply_markup=get_contact_method_keyboard(return_to_result),
    )
    await callback.answer()


@router.callback_query(lambda callback: callback.data.startswith("contact_method:"))
async def contact_method_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle selected contact delivery method and ask about staff reply."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    data = await state.get_data()
    animal = await get_last_result_animal(callback.from_user.id)

    result_animal = animal["name"] if animal is not None else "не указан"
    return_to_result = bool(data.get("return_to_result", animal is not None))

    _, contact_method = (callback.data or "").split(":")

    await safe_delete_callback_message(callback)

    await state.update_data(
        result_animal=result_animal,
        contact_method=contact_method,
        return_to_result=return_to_result,
    )
    await state.set_state(ContactStaffState.waiting_for_reply_method)

    await message.answer(
        "Нужен ли тебе ответ сотрудника зоопарка на это сообщение?",
        reply_markup=get_contact_reply_method_keyboard(return_to_result),
    )
    await callback.answer()


@router.callback_query(
    ContactStaffState.waiting_for_reply_method,
    F.data.startswith("contact_reply_method:"),
)
async def contact_reply_method_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle selected reply method for contact request."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    _, reply_method = (callback.data or "").split(":")
    data = await state.get_data()
    return_to_result = bool(data.get("return_to_result", False))

    if reply_method == "none":
        await state.update_data(
            contact_reply_method="none",
            contact_reply_contact=None,
        )
        await ask_contact_message(message, state)
        await callback.answer()
        return

    await state.update_data(contact_reply_method=reply_method)
    await state.set_state(ContactStaffState.waiting_for_reply_contact)

    if reply_method == "email":
        text = (
            "Введи email, на который сотрудник сможет ответить.\n\n"
            "Например: name@example.com\n\n"
            "Мы не сохраняем этот email в базе. "
            "Он будет использован только для ответа на твой запрос."
        )
    else:
        text = (
            "Введи Telegram-ник, на который сотрудник сможет ответить.\n\n"
            "Например: @username\n\n"
            "Мы не сохраняем этот Telegram-ник в базе. "
            "Он будет использован только для ответа на твой запрос."
        )

    sent_message = await message.answer(
        text,
        reply_markup=get_contact_reply_contact_keyboard(),
    )

    await state.update_data(
        contact_reply_contact_prompt_message_id=sent_message.message_id,
    )
    await callback.answer()


@router.callback_query(
    ContactStaffState.waiting_for_reply_contact,
    F.data == "contact_back_to_reply_method",
)
async def contact_back_to_reply_method_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Return user to contact reply method selection."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    data = await state.get_data()
    return_to_result = bool(data.get("return_to_result", False))

    await state.set_state(ContactStaffState.waiting_for_reply_method)

    await message.answer(
        "Нужен ли тебе ответ сотрудника зоопарка на это сообщение?",
        reply_markup=get_contact_reply_method_keyboard(return_to_result),
    )
    await callback.answer()


@router.message(ContactStaffState.waiting_for_reply_contact, F.text)
async def contact_reply_contact_handler(message: Message, state: FSMContext) -> None:
    """Receive reply contact and ask user to write message for staff."""

    if message.text is None:
        return

    data = await state.get_data()
    reply_method = data.get("contact_reply_method", "none")
    prompt_message_id = data.get("contact_reply_contact_prompt_message_id")

    reply_contact = message.text.strip()

    if reply_method == "email" and not is_valid_email(reply_contact):
        await safe_delete_message(message)

        await message.answer(
            "Почта выглядит некорректно. Введи email в формате name@example.com.\n\n"
            "Мы не сохраняем этот email в базе. "
            "Он будет использован только для ответа на твой запрос.",
            reply_markup=get_contact_reply_contact_keyboard(),
        )
        return

    if reply_method == "telegram":
        if not reply_contact:
            await safe_delete_message(message)

            await message.answer(
                "Telegram-ник не должен быть пустым. Например: @username\n\n"
                "Мы не сохраняем этот Telegram-ник в базе. "
                "Он будет использован только для ответа на твой запрос.",
                reply_markup=get_contact_reply_contact_keyboard(),
            )
            return

        if not reply_contact.startswith("@"):
            reply_contact = f"@{reply_contact}"

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)

    await state.update_data(contact_reply_contact=reply_contact)

    await ask_contact_message(message, state)


async def ask_contact_message(message: Message, state: FSMContext) -> None:
    """Ask user to write contact message for staff."""

    data = await state.get_data()

    result_animal = data.get("result_animal", "не указан")
    contact_method = data.get("contact_method", "telegram")
    return_to_result = bool(data.get("return_to_result", False))

    method_text = "в Telegram" if contact_method == "telegram" else "на почту"

    if result_animal != "не указан":
        prompt_text = (
            "Теперь напиши вопрос или сообщение для сотрудника зоопарка.\n\n"
            f"Я передам его {method_text} вместе с твоим результатом: "
            f"{result_animal} 🐾"
        )
    else:
        prompt_text = (
            "Теперь напиши вопрос или сообщение для сотрудника зоопарка.\n\n"
            "Если вопрос про опеку — можно сразу написать, какое животное тебе интересно 🐾"
        )

    sent_message = await message.answer(
        prompt_text,
        reply_markup=get_contact_cancel_keyboard(return_to_result),
    )

    await state.update_data(contact_prompt_message_id=sent_message.message_id)
    await state.set_state(ContactStaffState.waiting_for_message)


@router.message(ContactStaffState.waiting_for_message, F.text)
async def contact_message_handler(message: Message, state: FSMContext) -> None:
    """Receive user's contact message, deliver it and save to database."""

    if message.text is None:
        return

    data = await state.get_data()

    result_animal = data.get("result_animal", "не указан")
    contact_method = data.get("contact_method", "telegram")
    prompt_message_id = data.get("contact_prompt_message_id")
    return_to_result = bool(data.get("return_to_result", False))

    reply_method = data.get("contact_reply_method", "none")
    reply_contact = data.get("contact_reply_contact")

    user_text = message.text
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "не указан"
    )
    full_name = message.from_user.full_name

    if reply_method == "email":
        reply_text = f"Пользователь просит ответить на почту: {reply_contact}"
    elif reply_method == "telegram":
        reply_text = f"Пользователь просит ответить в Telegram: {reply_contact}"
    else:
        reply_text = "Ответ пользователю не требуется."

    staff_message = (
        "📩 Новое сообщение для сотрудника зоопарка\n\n"
        f"Пользователь: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {message.from_user.id}\n"
        f"Результат викторины: {result_animal}\n\n"
        f"Контакт для ответа:\n{reply_text}\n\n"
        f"Сообщение:\n{user_text}"
    )

    if contact_method == "telegram":
        prefix_text, delivery_status = await send_contact_to_telegram(
            message,
            staff_message,
        )
    else:
        prefix_text, delivery_status = await send_contact_to_email(
            subject=f"PythonZoo: сообщение от пользователя {full_name}",
            body=staff_message,
        )

    try:
        await save_contact_request(
            user=message.from_user,
            animal_name=result_animal,
            contact_method=contact_method,
            message_text=user_text,
            delivery_status=delivery_status,
        )
    except Exception:
        logger.exception("Failed to save contact request")

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)
    await state.clear()

    await message.answer(prefix_text)

    if return_to_result:
        await show_last_result(
            message=message,
            user_id=message.from_user.id,
        )
    else:
        await show_main_menu(
            message=message,
            user_id=message.from_user.id,
        )


async def send_contact_to_telegram(
    message: Message,
    staff_message: str,
) -> tuple[str, str]:
    """Send contact request to admin Telegram chat."""

    if settings.admin_chat_id <= 0:
        return (
            "Спасибо! Сообщение принято 🐾\n\n"
            "Сейчас Telegram-отправка работает в демонстрационном режиме: "
            "ADMIN_CHAT_ID не настроен.",
            "telegram_not_configured",
        )

    try:
        await message.bot.send_message(
            chat_id=settings.admin_chat_id,
            text=staff_message,
        )
        return (
            "Спасибо! Сообщение отправлено сотруднику в Telegram 🐾",
            "telegram_sent",
        )
    except TelegramAPIError:
        return (
            "Сообщение принято, но сейчас не удалось отправить его в Telegram. "
            "Проверь ADMIN_CHAT_ID или настройки доступа.",
            "telegram_failed",
        )


async def send_contact_to_email(subject: str, body: str) -> tuple[str, str]:
    """Send contact request to staff email."""

    try:
        await send_contact_email(
            subject=subject,
            body=body,
        )
        return (
            "Спасибо! Сообщение отправлено сотруднику на почту 🐾",
            "email_sent",
        )
    except Exception:
        return (
            "Сообщение принято, но сейчас не удалось отправить его на почту. "
            "Проверь настройки SMTP в .env.",
            "email_failed",
        )


@router.callback_query(lambda callback: callback.data == "leave_feedback")
async def leave_feedback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Start multi-step quiz feedback."""

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
    """Send current feedback rating question."""

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
    """Handle one feedback rating step."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    _, rating_text = (callback.data or "").split(":")
    rating = int(rating_text)

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
    """Restart feedback rating flow."""

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
    """Move feedback flow to reply method selection without text comment."""

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
    """Receive user's feedback comment and ask for reply method."""

    if message.text is None:
        return

    data = await state.get_data()
    prompt_message_id = data.get("feedback_comment_prompt_message_id")

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)

    await state.update_data(feedback_comment=message.text)
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
    """Handle selected reply method for feedback."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    _, reply_method = (callback.data or "").split(":")

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
    """Return user from reply contact input to reply method selection."""

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
    """Receive reply contact for feedback and finish feedback flow."""

    if message.text is None:
        return

    data = await state.get_data()
    reply_method = data.get("reply_method", "none")
    prompt_message_id = data.get("feedback_reply_contact_prompt_message_id")

    reply_contact = message.text.strip()

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
        if not reply_contact:
            await safe_delete_message(message)

            await message.answer(
                "Telegram-ник не должен быть пустым. Например: @username\n\n"
                "Мы не сохраняем этот Telegram-ник в базе. "
                "Он будет использован только для ответа на твой отзыв.",
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


@router.callback_query(lambda callback: callback.data == "cancel_action")
async def cancel_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current user action."""

    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    current_state = await state.get_state()
    data = await state.get_data()

    action_name = get_cancelled_action_name(
        current_state=current_state,
        quiz_active=False,
    )
    cancel_text = build_cancel_text(action_name)
    return_to_result = bool(data.get("return_to_result", True))

    await safe_delete_callback_message(callback)
    await state.clear()

    await message.answer(cancel_text)

    if return_to_result:
        await show_last_result(
            message=message,
            user_id=callback.from_user.id,
        )
    else:
        await show_main_menu(
            message=message,
            user_id=callback.from_user.id,
        )

    await callback.answer()


@router.callback_query(
    lambda callback: callback.data.startswith("feedback_rating:")
    or callback.data in {
        "skip_feedback_comment",
        "feedback_change_rating",
        "feedback_reply_method:none",
        "feedback_back_to_reply_method",
    }
)
async def stale_feedback_action_handler(callback: CallbackQuery) -> None:
    """Handle old feedback buttons."""

    await safe_delete_callback_message(callback)
    await callback.answer("Это действие уже неактуально 🙂")


def is_valid_email(email: str) -> bool:
    """Validate email format with a simple pattern."""

    return EMAIL_PATTERN.match(email.strip()) is not None


def build_feedback_staff_message(
    user: User,
    result_animal: str,
    ratings: dict,
    comment: str,
    reply_method: str,
    reply_contact: str | None,
) -> str:
    """Build feedback message for zoo staff."""

    username = f"@{user.username}" if user.username else "не указан"

    if reply_method == "email":
        reply_text = f"Пользователь просит ответить на почту: {reply_contact}"
    elif reply_method == "telegram":
        reply_text = f"Пользователь просит ответить в Telegram: {reply_contact}"
    else:
        reply_text = "Ответ пользователю не требуется."

    return (
        "⭐ Новый отзыв о викторине PythonZoo\n\n"
        f"Пользователь: {user.full_name}\n"
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


async def send_feedback_to_staff(
    bot: Bot,
    subject: str,
    body: str,
) -> tuple[str, bool, bool]:
    """Send feedback to staff via Telegram and email."""

    telegram_sent = False
    email_sent = False

    if settings.admin_chat_id > 0:
        try:
            await bot.send_message(
                chat_id=settings.admin_chat_id,
                text=body,
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
    """Send feedback to staff, save feedback to database and return to result."""

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
    except Exception:
        logger.exception("Failed to save feedback")

    await state.clear()

    await message.answer(delivery_text)

    await show_last_result(
        message=message,
        user_id=user.id,
    )