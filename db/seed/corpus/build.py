#!/usr/bin/env python3
"""
Render the talks to video and put them in the catalogue.

    uv run python db/seed/corpus/build.py

Needs `say` (macOS), ffmpeg, a database, and the media service running with an
S3 provider and INTERNAL_TOKEN set. Everything else the pipeline does from
there.

Idempotent by slug: re-running replaces the media and leaves the row, so a
change to a script can be re-ingested without a fresh database.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).parent))
from talks import TALKS  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://localhost:5432/loupe_dev")
MEDIA_URL = os.environ.get("MEDIA_SERVICE_URL", "http://127.0.0.1:8899")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")

CHANNEL_ID = "c0000000-0000-4000-b000-000000000001"
CHANNEL_HANDLE = "loupe-corpus"


def spoken(script: str) -> str:
    """The script as one line, which is what `say` wants and what ground truth is."""
    return re.sub(r"\s+", " ", script).strip()


def render(talk, workspace: Path) -> Path:
    """Speech plus a still frame, because the platform stores video."""
    aiff = workspace / f"{talk.slug}.aiff"
    mp4 = workspace / f"{talk.slug}.mp4"

    subprocess.run(
        ["say", "-v", "Daniel", "-r", "170", "-o", str(aiff), spoken(talk.script)],
        check=True,
    )

    # A still frame at 640x360 keeps these small — the corpus has to fit beside
    # everything else in 10 GB of free storage, and the picture carries nothing.
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=c=0x1f1f1f:s=640x360:r=5",
            "-i", str(aiff),
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "96k", "-shortest",
            str(mp4),
        ],
        check=True,
    )
    return mp4


async def sign(client: httpx.AsyncClient, key: str) -> str:
    response = await client.post(
        f"{MEDIA_URL}/v1/internal/sign",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        json={"key": key, "method": "PUT", "expires_in": 3600},
    )
    response.raise_for_status()
    return response.json()["url"]


async def main() -> int:
    if not INTERNAL_TOKEN:
        print("INTERNAL_TOKEN is not set; the media service will not sign uploads.")
        return 2

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2,
                                     statement_cache_size=0)

    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO channels (id, handle, name, description, source_class)
            VALUES ($1, $2, 'Loupe Corpus',
                    'Synthesised talks used to evaluate the semantic layer.', 'owned')
            ON CONFLICT (id) DO NOTHING
            """,
            CHANNEL_ID, CHANNEL_HANDLE,
        )

    with tempfile.TemporaryDirectory(prefix="loupe-corpus-") as directory:
        workspace = Path(directory)

        async with httpx.AsyncClient(timeout=httpx.Timeout(30, write=300)) as client:
            for talk in TALKS:
                print(f"  {talk.slug}: rendering…", flush=True)
                mp4 = render(talk, workspace)

                async with pool.acquire() as connection:
                    video_id = await connection.fetchval(
                        """
                        INSERT INTO videos
                          (source_class, channel_id, title, description,
                           processing_status, visibility, external_id)
                        VALUES ('owned', $1, $2, $3, 'uploaded', 'public', $4)
                        ON CONFLICT (source_class, external_id) DO UPDATE
                          SET processing_status = 'uploaded',
                              title = EXCLUDED.title
                        RETURNING id
                        """,
                        CHANNEL_ID, talk.title, talk.description,
                        f"corpus:{talk.slug}",
                    )
                    await connection.execute(
                        """
                        INSERT INTO video_assets (video_id, provider, provider_guid)
                        VALUES ($1, 's3', $2)
                        ON CONFLICT (video_id) DO UPDATE
                          SET provider = 's3', provider_guid = EXCLUDED.provider_guid
                        """,
                        video_id, str(video_id),
                    )
                    # A re-run must re-transcribe, or it would keep whatever the
                    # previous script produced and quietly evaluate stale text.
                    await connection.execute(
                        "DELETE FROM transcripts WHERE video_id = $1", video_id
                    )

                url = await sign(client, f"videos/{video_id}/source/original")
                response = await client.put(
                    url, content=mp4.read_bytes(),
                    headers={"Content-Type": "video/mp4"},
                )
                response.raise_for_status()

                size = mp4.stat().st_size / 1_048_576
                print(f"  {talk.slug}: uploaded {size:.1f} MB as {video_id}")

    await pool.close()
    print(f"\n{len(TALKS)} talks in the catalogue. Run the pipeline to process them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
