import logging

from redis.exceptions import RedisError

from bot.repositories.redis_client import get_redis_client


logger = logging.getLogger(__name__)


async def check_user_cooldown(
    user_id: int,
    action: str,
    seconds: int,
) -> tuple[bool, int]:
    redis_client = get_redis_client()
    key = f"python_zoo:rate_limit:{action}:{user_id}"

    try:
        created = await redis_client.set(
            key,
            "1",
            ex=seconds,
            nx=True,
        )

        if created:
            return True, 0

        ttl = await redis_client.ttl(key)
        return False, max(int(ttl), 0)

    # Rate limiting should not break the user flow if Redis has a short outage.
    # The action is allowed, but the problem is still logged.
    except RedisError:
        logger.warning(
            "Redis cooldown check failed, action is allowed action=%s user_id=%s",
            action,
            user_id,
        )
        return True, 0