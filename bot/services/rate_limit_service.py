from bot.repositories.redis_client import get_redis_client


async def check_user_cooldown(
    user_id: int,
    action: str,
    seconds: int,
) -> tuple[bool, int]:
    redis_client = get_redis_client()
    key = f"python_zoo:rate_limit:{action}:{user_id}"

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