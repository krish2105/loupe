from __future__ import annotations

import asyncpg

from .config import settings


def _checked_dsn(url: str) -> str:
    """
    Turn a bad DATABASE_URL into one sentence instead of a stack trace.

    asyncpg's own message for an unreplaced placeholder is `invalid DSN: scheme
    is expected to be either "postgresql" or "postgres", got ''`, under thirty
    lines of traceback through the connection pool. It is accurate and it does
    not say which variable, where it came from, or what it should look like.
    """
    if not url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            f"DATABASE_URL is not a connection string (got {url[:60]!r}).\n"
            "It must start with postgresql:// — for example\n"
            "  postgresql://postgres.<ref>:<password>@aws-0-<region>"
            ".pooler.supabase.com:6543/postgres\n"
            "If that looks like a placeholder, it was pasted without being "
            "replaced."
        )
    # asyncpg accepts both schemes; normalising means one form downstream.
    return url.replace("postgres://", "postgresql://", 1)



async def connect() -> asyncpg.Pool:
    """
    Open the pool.

    Unlike the API and media services this one raises when the database is
    unreachable. A worker with nowhere to write has nothing useful to do, and a
    cron job that exits non-zero is visible; one that runs happily and writes
    nothing is not.
    """
    dsn = _checked_dsn(settings.database_url)
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4, statement_cache_size=0)
