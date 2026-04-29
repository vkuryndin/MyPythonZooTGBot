from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard(
    has_result: bool,
    include_home_button: bool = False,
) -> InlineKeyboardMarkup:
    """Create the main menu keyboard.

    If user already has a quiz result, show additional result actions.
    """

    keyboard = []

    if has_result:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🎉 Посмотреть мой результат",
                    callback_data="back_to_result",
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                text=(
                    "🐾 Начать викторину"
                    if not has_result
                    else "🔁 Пройти викторину заново"
                ),
                callback_data="start_quiz",
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="ℹ️ Узнать про опеку",
                callback_data="about_adoption:main",
            )
        ]
    )

    if has_result:
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        text="📤 Поделиться результатом",
                        callback_data="share_result",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💬 Связаться с сотрудником",
                        callback_data="contact_staff",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⭐ Оставить отзыв",
                        callback_data="leave_feedback",
                    )
                ],
            ]
        )

    if include_home_button:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with a button back to the main menu."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Вернуться в главное меню",
                    callback_data="main_menu",
                )
            ]
        ]
    )


def get_back_to_result_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard with a button back to the last quiz result."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться к результату",
                    callback_data="back_to_result",
                )
            ]
        ]
    )

def get_adoption_keyboard(has_result: bool) -> InlineKeyboardMarkup:
    """Create keyboard for adoption information screen."""

    contact_callback = "contact_staff:result" if has_result else "contact_staff:main"
    back_callback = "back_to_result" if has_result else "main_menu"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Связаться с сотрудником",
                    callback_data=contact_callback,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться назад",
                    callback_data=back_callback,
                )
            ],
        ]
    )