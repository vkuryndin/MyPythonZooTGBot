from urllib.parse import quote

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import settings
from bot.handlers.menu import show_main_menu
from bot.keyboards.action_keyboards import (
    get_cancel_keyboard,
    get_feedback_comment_keyboard,
    get_feedback_rating_keyboard,
)
from bot.services.session_storage import get_last_result
from bot.states.user_states import ContactStaffState, FeedbackState


router = Router()


@router.callback_query(lambda callback: callback.data == "share_result")
async def share_result_handler(callback: CallbackQuery) -> None:
    """Show share message for user's quiz result."""

    animal = get_last_result(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    share_text = (
        f"Моё тотемное животное в Московском зоопарке — {animal['name']}! 🐾\n\n"
        "Пройди викторину и узнай своё."
    )

    share_url = (
        "https://t.me/share/url?"
        f"url={quote(settings.bot_link)}&"
        f"text={quote(share_text)}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться в Telegram",
                    url=share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Вернуться в главное меню",
                    callback_data="main_menu",
                )
            ],
        ]
    )

    await callback.message.answer(
        "Можно поделиться результатом в Telegram 👇",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(lambda callback: callback.data == "contact_staff")
async def contact_staff_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user to write a message for zoo staff."""

    animal = get_last_result(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    await state.update_data(result_animal=animal["name"])
    await state.set_state(ContactStaffState.waiting_for_message)

    await callback.message.answer(
        "Напиши вопрос или сообщение для сотрудника зоопарка.\n\n"
        f"Я передам его вместе с твоим результатом: {animal['name']} 🐾",
        reply_markup=get_cancel_keyboard(),
    )
    await callback.answer()


@router.message(ContactStaffState.waiting_for_message, F.text)
async def contact_message_handler(message: Message, state: FSMContext) -> None:
    """Receive user's contact message."""

    data = await state.get_data()
    result_animal = data.get("result_animal", "не указан")

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
        f"Сообщение:\n{message.text}"
    )

    if settings.admin_chat_id > 0:
        try:
            await message.bot.send_message(
                chat_id=settings.admin_chat_id,
                text=staff_message,
            )
            result_text = "Спасибо! Сообщение отправлено сотруднику зоопарка 🐾"
        except TelegramAPIError:
            result_text = (
                "Сообщение принято, но сейчас не удалось отправить его сотруднику. "
                "Позже мы сохраним такие заявки в PostgreSQL."
            )
    else:
        result_text = (
            "Спасибо! Сообщение принято 🐾\n\n"
            "Сейчас бот работает в демонстрационном режиме. "
            "На следующем этапе мы добавим сохранение заявки в PostgreSQL."
        )

    await state.clear()

    await show_main_menu(
        message=message,
        user_id=message.from_user.id,
        text=result_text,
    )


@router.callback_query(lambda callback: callback.data == "leave_feedback")
async def leave_feedback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user to rate the quiz."""

    animal = get_last_result(callback.from_user.id)

    await state.update_data(
        result_animal=animal["name"] if animal is not None else "не указан"
    )
    await state.set_state(FeedbackState.waiting_for_rating)

    await callback.message.answer(
        "Оцени, пожалуйста, викторину от 1 до 5 ⭐\n\n"
        "1 — совсем не понравилось\n"
        "5 — очень понравилось",
        reply_markup=get_feedback_rating_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    FeedbackState.waiting_for_rating,
    F.data.startswith("feedback_rating:"),
)
async def feedback_rating_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quiz rating."""

    await safe_remove_keyboard(callback)

    _, rating_text = callback.data.split(":")
    rating = int(rating_text)

    await state.update_data(rating=rating)
    await state.set_state(FeedbackState.waiting_for_comment)

    await callback.message.answer(
        f"Спасибо! Твоя оценка: {rating} из 5 ⭐\n\n"
        "Можешь ещё написать короткий комментарий: что понравилось, "
        "что улучшить или какого животного не хватило.",
        reply_markup=get_feedback_comment_keyboard(),
    )
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

    await safe_remove_keyboard(callback)

    await state.set_state(FeedbackState.waiting_for_rating)

    await callback.message.answer(
        "Выбери новую оценку викторины от 1 до 5 ⭐",
        reply_markup=get_feedback_rating_keyboard(),
    )
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

    await safe_remove_keyboard(callback)

    data = await state.get_data()
    rating = data.get("rating", "не указана")

    await state.clear()

    await show_main_menu(
        message=callback.message,
        user_id=callback.from_user.id,
        text=f"Спасибо за оценку! Ты поставил викторине {rating} из 5 ⭐",
    )
    await callback.answer()


@router.message(FeedbackState.waiting_for_comment, F.text)
async def feedback_comment_handler(message: Message, state: FSMContext) -> None:
    """Receive user's feedback comment."""

    data = await state.get_data()
    rating = data.get("rating", "не указана")

    await state.clear()

    await show_main_menu(
        message=message,
        user_id=message.from_user.id,
        text=(
            "Спасибо за отзыв! 🐾\n\n"
            f"Оценка: {rating} из 5 ⭐\n"
            "Комментарий принят. Он поможет сделать викторину лучше."
        ),
    )


@router.callback_query(lambda callback: callback.data == "cancel_action")
async def cancel_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel current user action."""

    await safe_remove_keyboard(callback)
    await state.clear()

    await show_main_menu(
        message=callback.message,
        user_id=callback.from_user.id,
        text="Действие отменено. Возвращаю в главное меню.",
    )
    await callback.answer()


@router.callback_query(
    lambda callback: callback.data.startswith("feedback_rating:")
    or callback.data in {"skip_feedback_comment", "feedback_change_rating"}
)
async def stale_feedback_action_handler(callback: CallbackQuery) -> None:
    """Handle old feedback buttons."""

    await safe_remove_keyboard(callback)
    await callback.answer("Это действие уже неактуально 🙂")


async def safe_remove_keyboard(callback: CallbackQuery) -> None:
    """Safely remove inline keyboard from callback message."""

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass