from aiogram import Router
from aiogram.types import CallbackQuery

from bot.keyboards.main_menu import get_main_menu_keyboard


router = Router()


@router.callback_query(lambda callback: callback.data == "about_adoption")
async def about_adoption_handler(callback: CallbackQuery) -> None:
    """Show information about the animal adoption program."""

    await callback.message.answer(
        "🐾 Программа «Возьми животное под опеку» помогает Московскому зоопарку "
        "заботиться о животных.\n\n"
        "Опекун поддерживает выбранного обитателя зоопарка, а зоопарк направляет "
        "эту помощь на питание, уход и улучшение условий жизни животного.\n\n"
        "После викторины я покажу твоё тотемное животное и расскажу, "
        "как можно узнать больше об опеке.",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()
