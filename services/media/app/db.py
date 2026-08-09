from __future__ import annotations

import asyncpg

from .config import settings

_pool: asyncpg.Pool | None = None


async def connect() -> asyncpg.Pool | None:
    """Open the pool. Returns None when unreachable so the service still starts."""
    global _pool
    if _pool is not None:
        return _pool

    try:
        dsn = settings.database_url.replace("postgres://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=5, statement_cache_size=0
        )
    except (OSError, asyncpg.PostgresError):
        _pool = None

    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool | None:
    return _pool
