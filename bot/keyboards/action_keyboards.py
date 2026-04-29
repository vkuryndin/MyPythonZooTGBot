from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_share_result_keyboard(
    telegram_share_url: str,
    vk_share_url: str,
    whatsapp_share_url: str,
    max_share_url: str,
) -> InlineKeyboardMarkup:
    """Create keyboard for sharing quiz result."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📨 Telegram",
                    url=telegram_share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="💙 ВКонтакте",
                    url=vk_share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟢 WhatsApp",
                    url=whatsapp_share_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟦 MAX",
                    url=max_share_url,
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


def get_contact_method_keyboard(return_to_result: bool = True) -> InlineKeyboardMarkup:
    """Create keyboard for choosing contact delivery method."""

    back_text = (
        "⬅️ Вернуться к результату"
        if return_to_result
        else "🏠 Вернуться в главное меню"
    )
    back_callback = "back_to_result" if return_to_result else "main_menu"

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
                    text=back_text,
                    callback_data=back_callback,
                )
            ],
        ]
    )


def get_contact_reply_method_keyboard(return_to_result: bool) -> InlineKeyboardMarkup:
    """Create keyboard for choosing whether staff should reply."""

    back_callback = "contact_staff:result" if return_to_result else "contact_staff:main"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Да, ответ на почту",
                    callback_data="contact_reply_method:email",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Да, ответ в Telegram",
                    callback_data="contact_reply_method:telegram",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🙌 Ответ не нужен",
                    callback_data="contact_reply_method:none",
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


def get_contact_reply_contact_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for contact reply contact input."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться назад",
                    callback_data="contact_back_to_reply_method",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Отменить и вернуться",
                    callback_data="cancel_action",
                )
            ],
        ]
    )


def get_contact_cancel_keyboard(return_to_result: bool = True) -> InlineKeyboardMarkup:
    """Create cancel keyboard for contact message input."""

    button_text = (
        "⬅️ Вернуться к результату"
        if return_to_result
        else "🏠 Вернуться в главное меню"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data="cancel_action",
                )
            ]
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Create default cancel action keyboard.

    Kept for compatibility with older handlers.
    """

    return get_contact_cancel_keyboard(return_to_result=True)


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


def get_feedback_reply_method_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for choosing feedback reply method."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Ответ на почту",
                    callback_data="feedback_reply_method:email",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Ответ в Telegram",
                    callback_data="feedback_reply_method:telegram",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🙌 Ответ не нужен",
                    callback_data="feedback_reply_method:none",
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


def get_feedback_reply_contact_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for feedback reply contact input."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Вернуться назад",
                    callback_data="feedback_back_to_reply_method",
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