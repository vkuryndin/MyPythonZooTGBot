from pathlib import Path
from typing import Any

from aiogram import Router
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


async def send_animal_result(
    message: Message,
    animal: dict[str, Any],
    prefix_text: str | None = None,
) -> None:
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
    await safe_delete_callback_message(callback)

    await show_last_result(
        message=callback.message,
        user_id=callback.from_user.id,
    )
    await callback.answer()


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