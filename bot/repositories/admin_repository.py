from typing import Any

from bot.repositories.database import get_pool


async def get_admin_stats() -> dict[str, Any]:
    pool = get_pool()

    row = await pool.fetchrow(
        """
        SELECT
            (SELECT COUNT(*) FROM quiz_results) AS quiz_results_count,
            (SELECT COUNT(*) FROM contact_requests) AS contact_requests_count,
            (SELECT COUNT(*) FROM feedback) AS feedback_count,
            (SELECT MAX(created_at) FROM quiz_results) AS last_quiz_result_at,
            (SELECT MAX(created_at) FROM contact_requests) AS last_contact_request_at,
            (SELECT MAX(created_at) FROM feedback) AS last_feedback_at
        """
    )

    return dict(row)


async def get_latest_contact_requests(limit: int = 5) -> list[dict[str, Any]]:
    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            telegram_user_id,
            username,
            full_name,
            animal_name,
            contact_method,
            message_text,
            delivery_status,
            created_at
        FROM contact_requests
        ORDER BY created_at DESC, id DESC
        LIMIT $1
        """,
        limit,
    )

    return [dict(row) for row in rows]


async def get_latest_feedback(limit: int = 5) -> list[dict[str, Any]]:
    pool = get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            animal_name,
            questions_quality,
            answers_quality,
            images_quality,
            navigation_quality,
            overall_quality,
            comment_text,
            telegram_sent,
            email_sent,
            created_at
        FROM feedback
        ORDER BY created_at DESC, id DESC
        LIMIT $1
        """,
        limit,
    )

    return [dict(row) for row in rows]