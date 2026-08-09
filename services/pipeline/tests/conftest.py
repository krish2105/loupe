import os
import uuid

import asyncpg
import pytest


@pytest.fixture
async def pool():
    dsn = os.environ.get(
        "DATABASE_URL", "postgres://localhost:5432/loupe_dev"
    ).replace("postgres://", "postgresql://", 1)

    try:
        created = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    except (OSError, asyncpg.PostgresError):
        pytest.skip("No database available")

    yield created
    await created.close()


@pytest.fixture
async def owned_video(pool):
    """
    One owned talk sitting at `transcoded`, ready for the first pipeline step.

    Class A on purpose: §4 forbids Class B from entering the pipeline at all,
    and the database enforces it, so a referenced fixture could not be used
    here even to test the negative case.
    """
    channel_id = uuid.uuid4()
    video_id = uuid.uuid4()

    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO channels (id, handle, name, source_class)
            VALUES ($1, $2, 'Pipeline Fixture', 'owned')
            """,
            channel_id,
            f"pf-{channel_id.hex[:8]}",
        )
        await connection.execute(
            """
            INSERT INTO videos
                (id, source_class, channel_id, title, processing_status, duration_sec)
            VALUES ($1, 'owned', $2, 'A talk', 'transcoded', 1800)
            """,
            video_id,
            channel_id,
        )
        await connection.execute(
            """
            INSERT INTO video_assets (video_id, provider, provider_guid, hls_url)
            VALUES ($1, 'demo', $2, 'https://example.invalid/master.m3u8')
            """,
            video_id,
            f"guid-{video_id.hex[:8]}",
        )

    yield video_id

    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute("SET LOCAL loupe.allow_purge = 'on'")
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)
            await connection.execute("DELETE FROM channels WHERE id = $1", channel_id)


async def status_of(pool, video_id) -> str:
    return await pool.fetchval(
        "SELECT processing_status::text FROM videos WHERE id = $1", video_id
    )


async def retries_of(pool, video_id) -> int:
    return await pool.fetchval("SELECT retry_count FROM videos WHERE id = $1", video_id)
