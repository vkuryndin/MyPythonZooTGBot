from pathlib import Path
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.keyboards.main_menu import get_main_menu_keyboard
from bot.keyboards.quiz_keyboards import get_result_keyboard
from bot.services.message_utils import safe_delete_callback_message
from bot.services.session_storage import get_last_result


router = Router()


def build_result_text(
    animal: dict[str, Any],
    prefix_text: str | None = None,
) -> str:
    """Build quiz result text."""

    result_text = (
        f"🎉 Твоё тотемное животное — {animal['name']}!\n\n"
        f"{animal['description']}"
    )

    if prefix_text:
        return f"{prefix_text}\n\n{result_text}"

    return result_text


async def send_animal_result(
    message: Message,
    animal: dict[str, Any],
    prefix_text: str | None = None,
) -> None:
    """Send animal result with photo if image exists."""

    result_text = build_result_text(
        animal=animal,
        prefix_text=prefix_text,
    )
    image_path = Path(animal["image_path"])

    if image_path.exists():
        photo = FSInputFile(image_path)
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
    """Show user's last quiz result or return to main menu."""

    animal = get_last_result(user_id)

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
    """Return user to the last quiz result screen."""

    await safe_delete_callback_message(callback)

    await show_last_result(
        message=callback.message,
        user_id=callback.from_user.id,
    )
    await callback.answer()