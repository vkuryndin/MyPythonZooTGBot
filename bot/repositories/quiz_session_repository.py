import json
import logging
import uuid
from typing import Any

from bot.repositories.redis_client import get_redis_client


logger = logging.getLogger(__name__)

QUIZ_SESSION_TTL_SECONDS = 60 * 60 * 2
QUIZ_ANSWER_LOCK_TTL_SECONDS = 10


def _quiz_session_key(user_id: int) -> str:
    return f"python_zoo:quiz_session:{user_id}"


def _quiz_answer_lock_key(user_id: int) -> str:
    return f"python_zoo:quiz_answer_lock:{user_id}"


async def create_quiz_session(
    user_id: int,
    question_order: list[int],
    option_orders: dict[str, list[int]],
) -> None:
    session = {
        "question_position": 0,
        "question_order": question_order,
        "option_orders": option_orders,
        "scores": {},
        "image_tags": [],
        "quiz_message_ids": [],
    }

    await save_quiz_session(user_id, session)


async def get_quiz_session(user_id: int) -> dict[str, Any] | None:
    redis_client = get_redis_client()
    raw_session = await redis_client.get(_quiz_session_key(user_id))

    if raw_session is None:
        return None

    try:
        return json.loads(raw_session)
    except json.JSONDecodeError:
        logger.warning("Corrupted quiz session removed user_id=%s", user_id)
        await redis_client.delete(_quiz_session_key(user_id))
        return None


async def save_quiz_session(user_id: int, session: dict[str, Any]) -> None:
    redis_client = get_redis_client()

    await redis_client.set(
        _quiz_session_key(user_id),
        json.dumps(session, ensure_ascii=False),
        ex=QUIZ_SESSION_TTL_SECONDS,
    )


async def delete_quiz_session(user_id: int) -> list[int]:
    redis_client = get_redis_client()
    session = await get_quiz_session(user_id)

    await redis_client.delete(_quiz_session_key(user_id))

    if session is None:
        return []

    return session.get("quiz_message_ids", [])


async def is_quiz_session_active(user_id: int) -> bool:
    redis_client = get_redis_client()
    exists = await redis_client.exists(_quiz_session_key(user_id))

    return bool(exists)


async def add_quiz_message_id(user_id: int, message_id: int) -> None:
    session = await get_quiz_session(user_id)

    if session is None:
        return

    session.setdefault("quiz_message_ids", []).append(message_id)

    await save_quiz_session(user_id, session)


async def add_scores(
    user_id: int,
    option_scores: dict[str, int],
) -> dict[str, int]:
    session = await get_quiz_session(user_id)

    if session is None:
        return {}

    scores = session.setdefault("scores", {})

    for animal_id, points in option_scores.items():
        scores[animal_id] = scores.get(animal_id, 0) + points

    await save_quiz_session(user_id, session)

    return scores


async def add_image_tags(user_id: int, image_tags: list[str]) -> list[str]:
    session = await get_quiz_session(user_id)

    if session is None:
        return []

    stored_tags = session.setdefault("image_tags", [])

    for tag in image_tags:
        if tag not in stored_tags:
            stored_tags.append(tag)

    await save_quiz_session(user_id, session)

    return stored_tags


async def set_question_position(user_id: int, question_position: int) -> None:
    session = await get_quiz_session(user_id)

    if session is None:
        return

    session["question_position"] = question_position

    await save_quiz_session(user_id, session)


async def set_question_index(user_id: int, question_index: int) -> None:
    await set_question_position(user_id, question_index)


async def acquire_quiz_answer_lock(user_id: int) -> str | None:
    redis_client = get_redis_client()
    token = uuid.uuid4().hex

    acquired = await redis_client.set(
        _quiz_answer_lock_key(user_id),
        token,
        ex=QUIZ_ANSWER_LOCK_TTL_SECONDS,
        nx=True,
    )

    if acquired:
        return token

    return None


async def release_quiz_answer_lock(user_id: int, token: str) -> None:
    redis_client = get_redis_client()

    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    await redis_client.eval(
        script,
        1,
        _quiz_answer_lock_key(user_id),
        token,
    )