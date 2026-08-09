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


_pool: asyncpg.Pool | None = None


async def connect() -> asyncpg.Pool | None:
    """Open the pool. Returns None when unreachable so the service still starts."""
    global _pool
    if _pool is not None:
        return _pool

    try:
        dsn = _checked_dsn(settings.database_url)
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
