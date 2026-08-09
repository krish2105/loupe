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
    # A password that is obviously still a placeholder. Postgres answers this
    # with `password authentication failed for user "postgres"`, which is true
    # and sends people to reset a password that was never wrong.
    password = ""
    if "@" in url:
        credentials = url.split("://", 1)[1].rsplit("@", 1)[0]
        password = credentials.split(":", 1)[1] if ":" in credentials else ""

    stripped = password.strip("[]<>{}").replace("-", "").replace("_", "").lower()
    if stripped in {"yourpassword", "password", "changeme", "yourdbpassword"} or (
        password.startswith("<") and password.endswith(">")
    ):
        raise RuntimeError(
            f"DATABASE_URL still has a placeholder password ({password!r}).\n"
            "Replace it with the real one from Supabase → Project Settings → "
            "Database.\n"
            "Set it once instead of pasting it repeatedly:\n"
            '  export LOUPE_DB="postgresql://...", then use "$LOUPE_DB"'
        )

    # asyncpg accepts both schemes; normalising means one form downstream.
    return url.replace("postgres://", "postgresql://", 1)


_pool: asyncpg.Pool | None = None


async def connect() -> asyncpg.Pool | None:
    """
    Open the connection pool.

    Returns None rather than raising when the database is unreachable. The API
    must still start and report its own health — an API that refuses to boot
    tells you nothing about why.
    """
    global _pool
    if _pool is not None:
        return _pool

    try:
        # asyncpg wants postgresql://, and Supabase hands out postgres://.
        dsn = _checked_dsn(settings.database_url)
        _pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=10,
            # statement_cache_size=0 is required, not tuning.
            #
            # Supabase's transaction pooler is PgBouncer in transaction mode,
            # where a connection is handed to a different client between
            # statements. asyncpg prepares statements by name and caches them,
            # so the second query on a recycled connection fails with
            # "prepared statement __asyncpg_stmt_1__ already exists" — a real
            # error that reads like a bug in this code and is not.
            #
            # Harmless on a direct connection, so it is set unconditionally
            # rather than branching on which URL happened to be configured.
            statement_cache_size=0,
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
