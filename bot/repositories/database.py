import asyncpg

from bot.config import settings


_pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """Create PostgreSQL connection pool."""

    global _pool

    _pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        min_size=1,
        max_size=5,
    )


async def close_db_pool() -> None:
    """Close PostgreSQL connection pool."""

    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return active PostgreSQL connection pool."""

    if _pool is None:
        raise RuntimeError("Database pool is not initialized")

    return _pool