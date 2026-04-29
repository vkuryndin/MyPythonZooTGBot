import re

from aiogram.types import CallbackQuery, Message


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}$"
)
TELEGRAM_USERNAME_PATTERN = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")

MAX_USER_TEXT_LENGTH = 1500
MAX_STAFF_MESSAGE_LENGTH = 3900
MAX_REPLY_CONTACT_LENGTH = 254


def get_callback_message(callback: CallbackQuery) -> Message | None:
    if isinstance(callback.message, Message):
        return callback.message

    return None


def limit_text(value: str | None, max_length: int) -> str:
    text = (value or "").strip()

    if len(text) <= max_length:
        return text

    return f"{text[:max_length]}…"


def is_valid_email(email: str) -> bool:
    email = email.strip()

    if len(email) > 254:
        return False

    if "\n" in email or "\r" in email:
        return False

    return EMAIL_PATTERN.match(email) is not None


def is_valid_telegram_username(username: str) -> bool:
    return TELEGRAM_USERNAME_PATTERN.match(username.strip()) is not None