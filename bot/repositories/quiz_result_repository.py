import json
from typing import Any

from aiogram.types import User

from bot.repositories.database import get_pool


async def save_quiz_result(
    user: User,
    animal: dict[str, Any],
    scores: dict[str, int],
) -> int:
    """Save quiz result to PostgreSQL and return created row id."""

    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO quiz_results (
            telegram_user_id,
            username,
            full_name,
            animal_id,
            animal_name,
            scores
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        RETURNING id
        """,
        user.id,
        user.username,
        user.full_name,
        animal["id"],
        animal["name"],
        json.dumps(scores, ensure_ascii=False),
    )

    return int(row["id"])