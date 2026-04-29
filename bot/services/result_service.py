from typing import Any

from bot.repositories.quiz_result_repository import get_last_quiz_result
from bot.services.quiz_service import quiz_service


async def get_last_result_animal(user_id: int) -> dict[str, Any] | None:
    """Get user's latest result animal from PostgreSQL."""

    result = await get_last_quiz_result(user_id)

    if result is None:
        return None

    animal_id = result["animal_id"]

    try:
        return quiz_service.get_animal_by_id(animal_id)
    except ValueError:
        return {
            "id": animal_id,
            "name": result["animal_name"],
            "image_path": "",
            "description": (
                "Результат найден, но описание животного больше не доступно "
                "в текущем файле animals.json."
            ),
        }


async def has_last_result(user_id: int) -> bool:
    """Check whether user has at least one saved quiz result."""

    return await get_last_quiz_result(user_id) is not None