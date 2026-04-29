from aiogram.types import User

from bot.repositories.database import get_pool


async def save_feedback(
    user: User,
    animal_name: str,
    ratings: dict,
    comment_text: str | None,
    telegram_sent: bool,
    email_sent: bool,
) -> int:
    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO feedback (
            telegram_user_id,
            username,
            full_name,
            animal_name,
            questions_quality,
            answers_quality,
            images_quality,
            navigation_quality,
            overall_quality,
            comment_text,
            telegram_sent,
            email_sent
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING id
        """,
        user.id,
        user.username,
        user.full_name,
        animal_name,
        int(ratings["questions_quality"]),
        int(ratings["answers_quality"]),
        int(ratings["images_quality"]),
        int(ratings["navigation_quality"]),
        int(ratings["overall_quality"]),
        comment_text,
        telegram_sent,
        email_sent,
    )

    return int(row["id"])