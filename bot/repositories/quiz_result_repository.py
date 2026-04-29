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

async def get_last_quiz_result(user_id: int) -> dict | None:
    """Get user's latest quiz result from PostgreSQL."""

    pool = get_pool()

    row = await pool.fetchrow(
        """
        SELECT
            animal_id,
            animal_name,
            scores,
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

    return dict(row)