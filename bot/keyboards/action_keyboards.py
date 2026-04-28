from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_contact_method_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for choosing contact delivery method."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 Отправить в Telegram",
                    callback_data="contact_method:telegram",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✉️ Отправить на почту",
                    callback_data="contact_method:email",
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


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Create cancel action keyboard."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться к результату",
                    callback_data="cancel_action",
                )
            ]
        ]
    )


def get_feedback_rating_keyboard() -> InlineKeyboardMarkup:
    """Create rating keyboard for quiz feedback."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="feedback_rating:1"),
                InlineKeyboardButton(text="2", callback_data="feedback_rating:2"),
                InlineKeyboardButton(text="3", callback_data="feedback_rating:3"),
                InlineKeyboardButton(text="4", callback_data="feedback_rating:4"),
                InlineKeyboardButton(text="5", callback_data="feedback_rating:5"),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться к результату",
                    callback_data="cancel_action",
                )
            ],
        ]
    )


def get_feedback_comment_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for optional feedback comment."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏭ Пропустить комментарий",
                    callback_data="skip_feedback_comment",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Изменить оценки",
                    callback_data="feedback_change_rating",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться к результату",
                    callback_data="cancel_action",
                )
            ],
        ]
    )