import logging

import asyncpg

from bot.config import settings


logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

DB_CONNECT_TIMEOUT_SECONDS = 5.0
DB_COMMAND_TIMEOUT_SECONDS = 30.0


async def init_db_pool() -> None:
    global _pool

    try:
        logger.info(
            "Initializing PostgreSQL connection pool host=%s port=%s database=%s",
            settings.db_host,
            settings.db_port,
            settings.db_name,
        )

        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            min_size=1,
            max_size=5,
            timeout=DB_CONNECT_TIMEOUT_SECONDS,
            command_timeout=DB_COMMAND_TIMEOUT_SECONDS,
        )

        logger.info("PostgreSQL connection pool initialized")
    except Exception:
        logger.exception(
            "Failed to initialize PostgreSQL connection pool. "
            "Check DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD and network access."
        )
        raise


async def close_db_pool() -> None:
    global _pool

    if _pool is not None:
        logger.info("Closing PostgreSQL connection pool")
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")

    return _pool