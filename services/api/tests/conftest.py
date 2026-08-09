import time
import uuid

import asyncpg
import httpx
import jwt
import pytest
from asgi_lifespan import LifespanManager

from app import db
from app.config import settings
from app.main import app

TEST_JWT_SECRET = "test-secret-not-used-anywhere-real"


@pytest.fixture(scope="session", autouse=True)
def jwt_secret():
    """
    Tests travel the real verification path with a test secret. There is no
    bypass in the application code, so this is the only way in — which is the
    point.
    """
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    yield
    settings.supabase_jwt_secret = ""


def token_for(user_id: uuid.UUID, *, expired: bool = False) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "exp": now - 60 if expired else now + 3600,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
async def client():
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
async def seeded(client):
    """
    A real user, channel, and owned video.

    Skips rather than fails when Postgres is absent, so `pytest` still runs on
    a machine without a database — but CI provides one, so these do execute.
    """
    pool = db.pool()
    if pool is None:
        pytest.skip("No database available")

    user_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    video_id = uuid.uuid4()

    async with pool.acquire() as connection:
        await connection.execute(
            "INSERT INTO channels (id, handle, name, source_class) VALUES ($1, $2, $3, 'owned')",
            channel_id,
            f"ch-{channel_id.hex[:8]}",
            "Test Channel",
        )
        await connection.execute(
            "INSERT INTO users (id, handle, display_name) VALUES ($1, $2, $3)",
            user_id,
            f"u-{user_id.hex[:8]}",
            "Test Person",
        )
        await connection.execute(
            """
            INSERT INTO videos
                (id, source_class, channel_id, title, processing_status, duration_sec)
            VALUES ($1, 'owned', $2, 'A talk', 'indexed', 3600)
            """,
            video_id,
            channel_id,
        )

    yield {"user_id": user_id, "video_id": video_id, "channel_id": channel_id}

    # watch_events is append-only, so teardown has to opt in explicitly —
    # exactly the path an account deletion would take.
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute("SET LOCAL loupe.allow_purge = 'on'")
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)
            await connection.execute("DELETE FROM users WHERE id = $1", user_id)
            await connection.execute("DELETE FROM channels WHERE id = $1", channel_id)


__all__ = ["asyncpg", "token_for", "seeded", "client"]
