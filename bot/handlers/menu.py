from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import (
    get_back_to_main_menu_keyboard,
    get_main_menu_keyboard,
)
from bot.services.session_storage import get_last_result


router = Router()


WELCOME_TEXT = (
    "Привет! 🐾\n\n"
    "Я бот Московского зоопарка. Помогу узнать, какое животное могло бы стать "
    "твоим тотемным.\n\n"
    "Ответь на несколько вопросов, а в конце я покажу результат."
)

MAIN_MENU_TEXT = (
    "Главное меню 🐾\n\n"
    "Выбери, что хочешь сделать:"
)


async def show_main_menu(
    message: Message,
    user_id: int,
    text: str | None = None,
    include_home_button: bool = False,
) -> None:
    """Send main menu with dynamic buttons."""

    has_result = get_last_result(user_id) is not None

    await message.answer(
        text or MAIN_MENU_TEXT,
        reply_markup=get_main_menu_keyboard(
            has_result=has_result,
            include_home_button=include_home_button,
        ),
    )


@router.callback_query(lambda callback: callback.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Show main menu."""

    await state.clear()

    await show_main_menu(
        message=callback.message,
        user_id=callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(lambda callback: callback.data == "about_adoption")
async def about_adoption_handler(callback: CallbackQuery) -> None:
    """Show information about the animal adoption program."""

    await callback.message.answer(
        "🐾 О программе опеки\n\n"
        "В Московском зоопарке можно взять животное под опеку и помогать "
        "заботиться о его питании, уходе и условиях жизни.\n\n"
        "Это способ поддержать зоопарк и внести вклад в сохранение "
        "биоразнообразия.\n\n"
        "После викторины ты можешь узнать своё тотемное животное, "
        "поделиться результатом или связаться с сотрудником зоопарка.",
        reply_markup=get_back_to_main_menu_keyboard(),
    )
    await callback.answer()