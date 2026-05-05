import logging
from datetime import datetime
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.repositories.admin_repository import (
    get_admin_stats,
    get_latest_contact_requests,
    get_latest_feedback,
)


router = Router()
logger = logging.getLogger(__name__)

ADMIN_HELP_TEXT = (
    "🔐 Админский режим MoscowZoo Spirit Animal\n\n"
    "Доступные команды:\n"
    "/admin_stats — статистика проекта\n"
    "/admin_contacts — последние обращения сотруднику\n"
    "/admin_feedback — последние отзывы"
)


def is_admin(message: Message) -> bool:
    if message.from_user is None:
        return False

    if settings.admin_chat_id <= 0:
        return False

    return message.from_user.id == settings.admin_chat_id


def get_user_id(message: Message) -> int | None:
    if message.from_user is None:
        return None

    return message.from_user.id


async def reject_non_admin(message: Message, command_name: str) -> None:
    logger.warning(
        "Unauthorized admin command attempt command=%s user_id=%s",
        command_name,
        get_user_id(message),
    )

    await message.answer("Эта команда доступна только администратору.")


def format_datetime(value: Any) -> str:
    if value is None:
        return "нет данных"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")

    return str(value)


def limit_text(value: str | None, max_length: int = 300) -> str:
    text = (value or "").strip()

    if not text:
        return "не указано"

    if len(text) <= max_length:
        return text

    return f"{text[:max_length]}…"


def format_username(username: str | None) -> str:
    if not username:
        return "не указан"

    if username.startswith("@"):
        return username

    return f"@{username}"


@router.message(Command("admin"))
async def admin_handler(message: Message) -> None:
    if not is_admin(message):
        await reject_non_admin(message, "/admin")
        return

    logger.info(
        "Admin command executed command=/admin user_id=%s",
        get_user_id(message),
    )

    await message.answer(ADMIN_HELP_TEXT)


@router.message(Command("admin_stats"))
async def admin_stats_handler(message: Message) -> None:
    if not is_admin(message):
        await reject_non_admin(message, "/admin_stats")
        return

    logger.info(
        "Admin command executed command=/admin_stats user_id=%s",
        get_user_id(message),
    )

    stats = await get_admin_stats()

    text = (
        "📊 Статистика SkillfactoryMoscowZooBot\n\n"
        f"Результатов викторины: {stats['quiz_results_count']}\n"
        f"Контактных заявок: {stats['contact_requests_count']}\n"
        f"Отзывов: {stats['feedback_count']}\n\n"
        f"Последний результат: {format_datetime(stats['last_quiz_result_at'])}\n"
        f"Последняя заявка: {format_datetime(stats['last_contact_request_at'])}\n"
        f"Последний отзыв: {format_datetime(stats['last_feedback_at'])}"
    )

    await message.answer(text)


@router.message(Command("admin_contacts"))
async def admin_contacts_handler(message: Message) -> None:
    if not is_admin(message):
        await reject_non_admin(message, "/admin_contacts")
        return

    logger.info(
        "Admin command executed command=/admin_contacts user_id=%s",
        get_user_id(message),
    )

    requests = await get_latest_contact_requests(limit=5)

    if not requests:
        await message.answer("📩 Контактных заявок пока нет.")
        return

    parts = ["📩 Последние обращения сотруднику\n"]

    for index, request in enumerate(requests, start=1):
        parts.append(
            "\n"
            f"{index}. Заявка #{request['id']}\n"
            f"Пользователь: {limit_text(request['full_name'], 80)}\n"
            f"Username: {format_username(request['username'])}\n"
            f"Telegram ID: {request['telegram_user_id']}\n"
            f"Животное: {request['animal_name']}\n"
            f"Способ: {request['contact_method']}\n"
            f"Статус: {request['delivery_status']}\n"
            f"Дата: {format_datetime(request['created_at'])}\n"
            f"Сообщение: {limit_text(request['message_text'])}\n"
        )

    await message.answer("\n".join(parts))


@router.message(Command("admin_feedback"))
async def admin_feedback_handler(message: Message) -> None:
    if not is_admin(message):
        await reject_non_admin(message, "/admin_feedback")
        return

    logger.info(
        "Admin command executed command=/admin_feedback user_id=%s",
        get_user_id(message),
    )

    feedback_items = await get_latest_feedback(limit=5)

    if not feedback_items:
        await message.answer("⭐ Отзывов пока нет.")
        return

    parts = ["⭐ Последние отзывы\n"]

    for index, feedback in enumerate(feedback_items, start=1):
        parts.append(
            "\n"
            f"{index}. Отзыв #{feedback['id']}\n"
            f"Животное: {feedback['animal_name']}\n"
            f"Оценки: "
            f"{feedback['questions_quality']}/"
            f"{feedback['answers_quality']}/"
            f"{feedback['images_quality']}/"
            f"{feedback['navigation_quality']}/"
            f"{feedback['overall_quality']}\n"
            f"Telegram отправлен: {'да' if feedback['telegram_sent'] else 'нет'}\n"
            f"Email отправлен: {'да' if feedback['email_sent'] else 'нет'}\n"
            f"Дата: {format_datetime(feedback['created_at'])}\n"
            f"Комментарий: {limit_text(feedback['comment_text'])}\n"
        )

    await message.answer("\n".join(parts))