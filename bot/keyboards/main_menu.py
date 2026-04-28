from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create the main menu keyboard."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐾 Начать викторину",
                    callback_data="start_quiz",
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ Узнать про опеку",
                    callback_data="about_adoption",
                )
            ],
        ]
    )