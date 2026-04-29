from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_question_keyboard(question: dict, question_index: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []

    for option_index, _ in enumerate(question["options"]):
        row.append(
            InlineKeyboardButton(
                text=str(option_index + 1),
                callback_data=f"quiz_answer:{question_index}:{option_index}",
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Завершить викторину",
                callback_data="cancel_quiz",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐾 Узнать про опеку",
                    callback_data="about_adoption:result",
                )
            ],
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
            [
                InlineKeyboardButton(
                    text="🔁 Пройти ещё раз",
                    callback_data="start_quiz",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎨 Сгенерировать ИИ-картинку",
                    callback_data="generate_result_image",
                )
            ],
        ]
    )