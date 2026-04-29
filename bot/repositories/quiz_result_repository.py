import json
from typing import Any

from aiogram.types import User

from bot.repositories.database import get_pool


def _decode_json_field(value: Any, default: Any) -> Any:
    if value is None:
        return default

    if isinstance(value, dict | list):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    return value


async def save_quiz_result(
    user: User,
    animal: dict[str, Any],
    scores: dict[str, int],
    image_tags: list[str] | None = None,
) -> None:
    pool = get_pool()

    await pool.execute(
        """
        INSERT INTO quiz_results (
            telegram_user_id,
            username,
            full_name,
            animal_id,
            animal_name,
            scores,
            image_tags
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
        """,
        user.id,
        user.username,
        user.full_name,
        animal["id"],
        animal["name"],
        json.dumps(scores, ensure_ascii=False),
        json.dumps(image_tags or [], ensure_ascii=False),
    )


async def get_last_quiz_result(user_id: int) -> dict[str, Any] | None:
    pool = get_pool()

    row = await pool.fetchrow(
        """
        SELECT
            animal_id,
            animal_name,
            scores,
            image_tags,
            created_at
        FROM quiz_results
        WHERE telegram_user_id = $1
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        user_id,
    )

    if row is None:
        return None

    result = dict(row)
    result["scores"] = _decode_json_field(result.get("scores"), {})
    result["image_tags"] = _decode_json_field(result.get("image_tags"), [])

    return result