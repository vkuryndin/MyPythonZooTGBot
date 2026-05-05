from pathlib import Path
from typing import Any

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.keyboards.main_menu import get_main_menu_keyboard
from bot.keyboards.quiz_keyboards import get_result_keyboard
from bot.services.message_utils import safe_delete_callback_message
from bot.services.result_service import get_last_result_animal


router = Router()


def build_result_text(
    animal: dict[str, Any],
    prefix_text: str | None = None,
) -> str:
    text = (
        f"🎉 Твоё тотемное животное — {animal['name']}!\n\n"
        f"{animal['description']}"
    )

    return f"{prefix_text}\n\n{text}" if prefix_text else text


def get_callback_message(callback: CallbackQuery) -> Message | None:
    if isinstance(callback.message, Message):
        return callback.message

    return None


async def safe_answer_callback(
    callback: CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(
            text=text,
            show_alert=show_alert,
        )
    except TelegramBadRequest as error:
        if is_expired_callback_error(error):
            return

        raise


def is_expired_callback_error(error: Exception) -> bool:
    if not isinstance(error, TelegramBadRequest):
        return False

    message = str(error)

    return (
        "query is too old" in message
        or "response timeout expired" in message
        or "query ID is invalid" in message
    )


async def send_animal_result(
    message: Message,
    animal: dict[str, Any],
    prefix_text: str | None = None,
) -> None:
    result_text = build_result_text(
        animal=animal,
        prefix_text=prefix_text,
    )
    image_path_value = animal.get("image_path")

    # Fallback results may have an empty image path.
    # Check for a real file before trying to send a photo.
    if image_path_value and Path(image_path_value).is_file():
        photo = FSInputFile(image_path_value)
        await message.answer_photo(
            photo=photo,
            caption=result_text,
            reply_markup=get_result_keyboard(),
        )
    else:
        await message.answer(
            result_text,
            reply_markup=get_result_keyboard(),
        )


async def show_last_result(
    message: Message,
    user_id: int,
    prefix_text: str | None = None,
) -> None:
    animal = await get_last_result_animal(user_id)

    if animal is None:
        await message.answer(
            "Результат не найден. Пройди викторину ещё раз 🐾",
            reply_markup=get_main_menu_keyboard(has_result=False),
        )
        return

    await send_animal_result(
        message=message,
        animal=animal,
        prefix_text=prefix_text,
    )


@router.callback_query(lambda callback: callback.data == "back_to_result")
async def back_to_result_handler(callback: CallbackQuery) -> None:
    message = get_callback_message(callback)

    if message is None:
        await safe_answer_callback(callback, "Сообщение уже недоступно 🙂")
        return

    await safe_answer_callback(callback)

    await safe_delete_callback_message(callback)

    await show_last_result(
        message=message,
        user_id=callback.from_user.id,
    )


async def send_result_actions_menu(
    message: Message,
    animal: dict[str, Any],
    include_view_result_button: bool = False,
) -> None:
    await message.answer(
        f"Что хочешь сделать дальше с результатом {animal['name']}? 🐾",
        reply_markup=get_result_keyboard(
            include_view_result_button=include_view_result_button
        ),
    )