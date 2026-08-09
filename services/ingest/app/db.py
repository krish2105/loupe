from __future__ import annotations

import asyncpg

from .config import settings


async def connect() -> asyncpg.Pool:
    """
    Open the pool.

    Unlike the API and media services this one raises when the database is
    unreachable. A worker with nowhere to write has nothing useful to do, and a
    cron job that exits non-zero is visible; one that runs happily and writes
    nothing is not.
    """
    dsn = settings.database_url.replace("postgres://", "postgresql://", 1)
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)
