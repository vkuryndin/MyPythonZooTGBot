from aiogram.types import User

from bot.repositories.database import get_pool


async def save_contact_request(
    user: User,
    animal_name: str,
    contact_method: str,
    message_text: str,
    delivery_status: str,
) -> int:
    """Save contact request to PostgreSQL and return created row id."""

    pool = get_pool()

    row = await pool.fetchrow(
        """
        INSERT INTO contact_requests (
            telegram_user_id,
            username,
            full_name,
            animal_name,
            contact_method,
            message_text,
            delivery_status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        user.id,
        user.username,
        user.full_name,
        animal_name,
        contact_method,
        message_text,
        delivery_status,
    )

    return int(row["id"])