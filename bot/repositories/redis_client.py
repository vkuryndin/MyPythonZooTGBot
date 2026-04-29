import redis.asyncio as redis

from bot.config import settings


_redis_client: redis.Redis | None = None


async def init_redis_client() -> redis.Redis:
    """Create Redis client and check connection."""

    global _redis_client

    _redis_client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    await _redis_client.ping()

    return _redis_client


def get_redis_client() -> redis.Redis:
    """Return active Redis client."""

    if _redis_client is None:
        raise RuntimeError("Redis client is not initialized")

    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client."""

    global _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None