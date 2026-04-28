from urllib.parse import quote

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import settings
from bot.handlers.result_view import show_last_result
from bot.keyboards.action_keyboards import (
    get_cancel_keyboard,
    get_contact_method_keyboard,
    get_feedback_comment_keyboard,
    get_feedback_rating_keyboard,
)
from bot.services.email_service import send_contact_email
from bot.services.message_utils import (
    safe_delete_callback_message,
    safe_delete_message,
    safe_delete_message_by_id,
)
from bot.services.session_storage import get_last_result
from bot.states.user_states import ContactStaffState, FeedbackState


router = Router()


@router.callback_query(lambda callback: callback.data == "share_result")
async def share_result_handler(callback: CallbackQuery) -> None:
    """Show social share buttons for user's quiz result."""

    animal = get_last_result(callback.from_user.id)

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

    vk_share_url = (
        "https://vk.com/share.php?"
        f"url={encoded_bot_link}"
    )

    whatsapp_share_url = (
        "https://api.whatsapp.com/send?"
        f"text={encoded_full_text}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 Telegram",
                    url=telegram_share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="💙 ВКонтакте",
                    url=vk_share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟢 WhatsApp",
                    url=whatsapp_share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться к результату",
                    callback_data="back_to_result",
                )
            ],
        ]
    )

    await callback.message.answer(
        "Выбери, где хочешь поделиться результатом 👇",
        reply_markup=keyboard,
    )
    await callback.answer()

@router.callback_query(lambda callback: callback.data == "contact_staff")
async def contact_staff_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user to choose contact delivery method."""

    animal = get_last_result(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    await safe_delete_callback_message(callback)
    await state.clear()

    await callback.message.answer(
        "Как передать сообщение сотруднику зоопарка?",
        reply_markup=get_contact_method_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda callback: callback.data.startswith("contact_method:"))
async def contact_method_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle selected contact delivery method."""

    animal = get_last_result(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    _, contact_method = callback.data.split(":")

    await safe_delete_callback_message(callback)

    method_text = (
        "в Telegram"
        if contact_method == "telegram"
        else "на почту"
    )

    sent_message = await callback.message.answer(
        "Напиши вопрос или сообщение для сотрудника зоопарка.\n\n"
        f"Я передам его {method_text} вместе с твоим результатом: "
        f"{animal['name']} 🐾",
        reply_markup=get_cancel_keyboard(),
    )

    await state.update_data(
        result_animal=animal["name"],
        contact_method=contact_method,
        contact_prompt_message_id=sent_message.message_id,
    )
    await state.set_state(ContactStaffState.waiting_for_message)

    await callback.answer()



@router.message(ContactStaffState.waiting_for_message, F.text)
async def contact_message_handler(message: Message, state: FSMContext) -> None:
    """Receive user's contact message and deliver it by selected method."""

    data = await state.get_data()
    result_animal = data.get("result_animal", "не указан")
    contact_method = data.get("contact_method", "telegram")
    prompt_message_id = data.get("contact_prompt_message_id")

    user_text = message.text
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "не указан"
    )
    full_name = message.from_user.full_name

    staff_message = (
        "📩 Новое сообщение для сотрудника зоопарка\n\n"
        f"Пользователь: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {message.from_user.id}\n"
        f"Результат викторины: {result_animal}\n\n"
        f"Сообщение:\n{user_text}"
    )

    if contact_method == "telegram":
        prefix_text = await send_contact_to_telegram(message, staff_message)
    else:
        prefix_text = await send_contact_to_email(
            subject=f"PythonZoo: сообщение от пользователя {full_name}",
            body=staff_message,
        )

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)
    await state.clear()

    await message.answer(prefix_text)

    await show_last_result(
        message=message,
        user_id=message.from_user.id,
    )


async def send_contact_to_telegram(message: Message, staff_message: str) -> str:
    """Send contact request to admin Telegram chat."""

    if settings.admin_chat_id <= 0:
        return (
            "Спасибо! Сообщение принято 🐾\n\n"
            "Сейчас Telegram-отправка работает в демонстрационном режиме: "
            "ADMIN_CHAT_ID не настроен."
        )

    try:
        await message.bot.send_message(
            chat_id=settings.admin_chat_id,
            text=staff_message,
        )
        return "Спасибо! Сообщение отправлено сотруднику в Telegram 🐾"
    except TelegramAPIError:
        return (
            "Сообщение принято, но сейчас не удалось отправить его в Telegram. "
            "Позже мы сохраним такие заявки в PostgreSQL."
        )


async def send_contact_to_email(subject: str, body: str) -> str:
    """Send contact request to staff email."""

    try:
        await send_contact_email(
            subject=subject,
            body=body,
        )
        return "Спасибо! Сообщение отправлено сотруднику на почту 🐾"
    except Exception:
        return (
            "Сообщение принято, но сейчас не удалось отправить его на почту. "
            "Проверь настройки SMTP в .env."
        )



@router.callback_query(lambda callback: callback.data == "leave_feedback")
async def leave_feedback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user to rate the quiz."""

    animal = get_last_result(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    await safe_delete_callback_message(callback)

    sent_message = await callback.message.answer(
        "Оцени, пожалуйста, викторину от 1 до 5 ⭐\n\n"
        "1 — совсем не понравилось\n"
        "5 — очень понравилось",
        reply_markup=get_feedback_rating_keyboard(),
    )

    await state.update_data(
        result_animal=animal["name"],
        feedback_rating_prompt_message_id=sent_message.message_id,
    )
    await state.set_state(FeedbackState.waiting_for_rating)

    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_for_rating,
    F.data.startswith("feedback_rating:"),
)
async def feedback_rating_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quiz rating."""

    await safe_delete_callback_message(callback)

    _, rating_text = callback.data.split(":")
    rating = int(rating_text)

    sent_message = await callback.message.answer(
        f"Спасибо! Твоя оценка: {rating} из 5 ⭐\n\n"
        "Можешь ещё написать короткий комментарий: что понравилось, "
        "что улучшить или какого животного не хватило.",
        reply_markup=get_feedback_comment_keyboard(),
    )

    await state.update_data(
        rating=rating,
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
    """Return user to feedback rating step."""

    await safe_delete_callback_message(callback)

    sent_message = await callback.message.answer(
        "Выбери новую оценку викторины от 1 до 5 ⭐",
        reply_markup=get_feedback_rating_keyboard(),
    )

    await state.update_data(
        feedback_rating_prompt_message_id=sent_message.message_id,
    )
    await state.set_state(FeedbackState.waiting_for_rating)

    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_for_comment,
    F.data == "skip_feedback_comment",
)
async def skip_feedback_comment_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Finish feedback without text comment."""

    await safe_delete_callback_message(callback)

    data = await state.get_data()
    rating = data.get("rating", "не указана")

    await state.clear()

    await callback.message.answer(
        f"Спасибо за оценку! Ты поставил викторине {rating} из 5 ⭐"
    )

    await show_last_result(
        message=callback.message,
        user_id=callback.from_user.id,
    )

    await callback.answer()


@router.message(FeedbackState.waiting_for_comment, F.text)
async def feedback_comment_handler(message: Message, state: FSMContext) -> None:
    """Receive user's feedback comment."""

    data = await state.get_data()
    rating = data.get("rating", "не указана")
    prompt_message_id = data.get("feedback_comment_prompt_message_id")

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)
    await state.clear()

    await message.answer(
        "Спасибо за отзыв! 🐾\n\n"
        f"Оценка: {rating} из 5 ⭐\n"
        "Комментарий принят. Он поможет сделать викторину лучше."
    )

    await show_last_result(
        message=message,
        user_id=message.from_user.id,
    )


@router.callback_query(lambda callback: callback.data == "cancel_action")
async def cancel_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current user action."""

    await safe_delete_callback_message(callback)
    await state.clear()

    await callback.message.answer("Действие отменено.")

    await show_last_result(
        message=callback.message,
        user_id=callback.from_user.id,
    )

    await callback.answer()


@router.callback_query(
    lambda callback: callback.data.startswith("feedback_rating:")
    or callback.data in {"skip_feedback_comment", "feedback_change_rating"}
)
async def stale_feedback_action_handler(callback: CallbackQuery) -> None:
    """Handle old feedback buttons."""

    await safe_delete_callback_message(callback)
    await callback.answer("Это действие уже неактуально 🙂")