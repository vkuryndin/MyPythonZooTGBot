import logging

import redis.asyncio as redis

from bot.config import settings


logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


async def init_redis_client() -> redis.Redis:
    global _redis_client

    try:
        logger.info("Initializing Redis client")

        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        await _redis_client.ping()

        logger.info("Redis client initialized")
        return _redis_client
    except Exception:
        logger.exception("Failed to initialize Redis client")
        raise


def get_redis_client() -> redis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialized")

    return _redis_client


async def close_redis_client() -> None:
    global _redis_client

    if _redis_client is not None:
        logger.info("Closing Redis client")
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")