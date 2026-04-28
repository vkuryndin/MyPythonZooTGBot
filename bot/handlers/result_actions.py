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
from bot.services.action_names import build_cancel_text, get_cancelled_action_name

router = Router()

FEEDBACK_STEPS = [
    ("questions_quality", "качество и понятность вопросов"),
    ("answers_quality", "качество и оригинальность ответов"),
    ("images_quality", "качество картинок"),
    ("navigation_quality", "понятность бота, меню и общей навигации"),
    ("overall_quality", "викторину в целом"),
]


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
    """Start multi-step quiz feedback."""

    animal = get_last_result(callback.from_user.id)

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

    await send_feedback_rating_question(callback.message, state)
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

    await safe_delete_callback_message(callback)

    _, rating_text = callback.data.split(":")
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
        await send_feedback_rating_question(callback.message, state)
    else:
        sent_message = await callback.message.answer(
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

    await safe_delete_callback_message(callback)

    data = await state.get_data()
    result_animal = data.get("result_animal", "не указан")

    await state.update_data(
        result_animal=result_animal,
        feedback_step=0,
        feedback_ratings={},
    )
    await state.set_state(FeedbackState.waiting_for_rating)

    await send_feedback_rating_question(callback.message, state)
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
    await state.clear()

    feedback_message = build_feedback_staff_message(
        user=callback.from_user,
        result_animal=data.get("result_animal", "не указан"),
        ratings=data.get("feedback_ratings", {}),
        comment="Комментарий не оставлен.",
    )

    delivery_text = await send_feedback_to_staff(
        bot=callback.bot,
        subject="PythonZoo: новый отзыв о викторине",
        body=feedback_message,
    )

    await callback.message.answer(delivery_text)

    await show_last_result(
        message=callback.message,
        user_id=callback.from_user.id,
    )

    await callback.answer()


@router.message(FeedbackState.waiting_for_comment, F.text)
async def feedback_comment_handler(message: Message, state: FSMContext) -> None:
    """Receive user's feedback comment and send it to staff."""

    data = await state.get_data()
    prompt_message_id = data.get("feedback_comment_prompt_message_id")

    feedback_message = build_feedback_staff_message(
        user=message.from_user,
        result_animal=data.get("result_animal", "не указан"),
        ratings=data.get("feedback_ratings", {}),
        comment=message.text,
    )

    delivery_text = await send_feedback_to_staff(
        bot=message.bot,
        subject="PythonZoo: новый отзыв о викторине",
        body=feedback_message,
    )

    await safe_delete_message_by_id(message, prompt_message_id)
    await safe_delete_message(message)
    await state.clear()

    await message.answer(delivery_text)

    await show_last_result(
        message=message,
        user_id=message.from_user.id,
    )


@router.callback_query(lambda callback: callback.data == "cancel_action")
async def cancel_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current user action."""

    current_state = await state.get_state()
    action_name = get_cancelled_action_name(
        current_state=current_state,
        quiz_active=False,
    )
    cancel_text = build_cancel_text(action_name)

    await safe_delete_callback_message(callback)
    await state.clear()

    await callback.message.answer(cancel_text)

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


def build_feedback_staff_message(
    user,
    result_animal: str,
    ratings: dict,
    comment: str,
) -> str:
    """Build feedback message for zoo staff."""

    username = f"@{user.username}" if user.username else "не указан"

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
        f"Комментарий:\n{comment}"
    )


async def send_feedback_to_staff(bot, subject: str, body: str) -> str:
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
            "Мы отправили его сотруднику в Telegram и на почту."
        )

    if telegram_sent and not email_sent:
        return (
            "Спасибо за отзыв! 🐾\n\n"
            "Отзыв отправлен в Telegram. На почту отправить не удалось — "
            "проверь настройки SMTP в .env."
        )

    if email_sent and not telegram_sent:
        return (
            "Спасибо за отзыв! 🐾\n\n"
            "Отзыв отправлен на почту. В Telegram отправить не удалось — "
            "проверь ADMIN_CHAT_ID."
        )

    return (
        "Спасибо за отзыв! 🐾\n\n"
        "Сейчас не удалось отправить его сотруднику. "
        "Проверь ADMIN_CHAT_ID и SMTP-настройки в .env."
    )