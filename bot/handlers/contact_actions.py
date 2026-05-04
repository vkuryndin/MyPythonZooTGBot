import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asyncpg.exceptions import PostgresError

from bot.config import settings
from bot.handlers.menu import show_main_menu
from bot.handlers.result_view import show_last_result
from bot.keyboards.action_keyboards import (
    get_contact_cancel_keyboard,
    get_contact_method_keyboard,
    get_contact_reply_contact_keyboard,
    get_contact_reply_method_keyboard,
)
from bot.repositories.contact_repository import save_contact_request
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
from bot.states.user_states import ContactStaffState


router = Router()
logger = logging.getLogger(__name__)

CONTACT_COOLDOWN_SECONDS = 300

CONTACT_METHODS = {"telegram", "email"}
CONTACT_REPLY_METHODS = {"email", "telegram", "none"}


def get_callback_value(callback_data: str | None, prefix: str) -> str | None:
    if not callback_data or not callback_data.startswith(prefix):
        return None

    return callback_data[len(prefix):]


@router.callback_query(
    lambda callback: callback.data in {
        "contact_staff",
        "contact_staff:main",
        "contact_staff:result",
    }
)
async def contact_staff_handler(callback: CallbackQuery, state: FSMContext) -> None:
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


@router.callback_query(
    lambda callback: bool(
        callback.data and callback.data.startswith("contact_method:")
    )
)
async def contact_method_handler(callback: CallbackQuery, state: FSMContext) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    contact_method = get_callback_value(callback.data, "contact_method:")

    if contact_method not in CONTACT_METHODS:
        logger.warning(
            "Invalid contact method callback user_id=%s value=%s",
            callback.from_user.id,
            contact_method,
        )
        await callback.answer("Некорректное действие 🙂")
        return

    data = await state.get_data()
    animal = await get_last_result_animal(callback.from_user.id)

    result_animal = animal["name"] if animal is not None else "не указан"
    return_to_result = data.get("return_to_result", animal is not None)

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
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    reply_method = get_callback_value(callback.data, "contact_reply_method:")

    if reply_method not in CONTACT_REPLY_METHODS:
        logger.warning(
            "Invalid contact reply method callback user_id=%s value=%s",
            callback.from_user.id,
            reply_method,
        )
        await callback.answer("Некорректное действие 🙂")
        return

    await safe_delete_callback_message(callback)

    data = await state.get_data()
    return_to_result = data.get("return_to_result", False)

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
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    await safe_delete_callback_message(callback)

    data = await state.get_data()
    return_to_result = data.get("return_to_result", False)

    await state.set_state(ContactStaffState.waiting_for_reply_method)

    await message.answer(
        "Нужен ли тебе ответ сотрудника зоопарка на это сообщение?",
        reply_markup=get_contact_reply_method_keyboard(return_to_result),
    )
    await callback.answer()


@router.message(ContactStaffState.waiting_for_reply_contact, F.text)
async def contact_reply_contact_handler(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    data = await state.get_data()
    reply_method = data.get("contact_reply_method", "none")
    prompt_message_id = data.get("contact_reply_contact_prompt_message_id")

    if reply_method not in CONTACT_REPLY_METHODS:
        logger.warning(
            "Invalid stored contact reply method user_id=%s value=%s",
            message.from_user.id,
            reply_method,
        )
        await state.clear()
        await message.answer("Сценарий устарел. Попробуй начать заново 🙂")
        return

    reply_contact = limit_text(message.text, MAX_REPLY_CONTACT_LENGTH)

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
        if not is_valid_telegram_username(reply_contact):
            await safe_delete_message(message)

            await message.answer(
                "Telegram-ник выглядит некорректно. Введи ник в формате @username.",
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
    data = await state.get_data()

    result_animal = data.get("result_animal", "не указан")
    contact_method = data.get("contact_method", "telegram")
    return_to_result = data.get("return_to_result", False)

    if contact_method not in CONTACT_METHODS:
        logger.warning(
            "Invalid stored contact method user_id=%s value=%s",
            message.from_user.id,
            contact_method,
        )
        await state.clear()
        await message.answer("Сценарий устарел. Попробуй начать заново 🙂")
        return

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
    if message.text is None:
        return

    data = await state.get_data()

    result_animal = data.get("result_animal", "не указан")
    contact_method = data.get("contact_method", "telegram")
    prompt_message_id = data.get("contact_prompt_message_id")
    return_to_result = data.get("return_to_result", False)

    reply_method = data.get("contact_reply_method", "none")
    reply_contact = data.get("contact_reply_contact")

    if contact_method not in CONTACT_METHODS:
        logger.warning(
            "Invalid stored contact method before sending user_id=%s value=%s",
            message.from_user.id,
            contact_method,
        )
        await state.clear()
        await message.answer("Сценарий устарел. Попробуй начать заново 🙂")
        return

    if reply_method not in CONTACT_REPLY_METHODS:
        logger.warning(
            "Invalid stored contact reply method before sending user_id=%s value=%s",
            message.from_user.id,
            reply_method,
        )
        await state.clear()
        await message.answer("Сценарий устарел. Попробуй начать заново 🙂")
        return

    allowed, retry_after = await check_user_cooldown(
        user_id=message.from_user.id,
        action="contact_staff",
        seconds=CONTACT_COOLDOWN_SECONDS,
    )

    if not allowed:
        await safe_delete_message_by_id(message, prompt_message_id)
        await safe_delete_message(message)
        await state.clear()

        await message.answer(
            "Сообщение сотруднику можно отправлять не чаще одного раза в 5 минут.\n"
            f"Попробуй ещё раз примерно через {retry_after} сек."
        )

        if return_to_result:
            await show_last_result(message=message, user_id=message.from_user.id)
        else:
            await show_main_menu(message=message, user_id=message.from_user.id)

        return

    user_text = limit_text(message.text, MAX_USER_TEXT_LENGTH)
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "не указан"
    )
    full_name = limit_text(message.from_user.full_name, 120)

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
    staff_message = limit_text(staff_message, MAX_STAFF_MESSAGE_LENGTH)

    if contact_method == "telegram":
        prefix_text, delivery_status = await send_contact_to_telegram(
            message,
            staff_message,
        )
    else:
        prefix_text, delivery_status = await send_contact_to_email(
            subject=f"MoscowZoo Spirit Animal: сообщение от пользователя {full_name}",
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
    except PostgresError:
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
            parse_mode=None,
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