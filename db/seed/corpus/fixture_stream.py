#!/usr/bin/env python3
"""
Host the placeholder stream ourselves instead of borrowing one.

    DATABASE_URL=... MEDIA_SERVICE_URL=... INTERNAL_TOKEN=... \\
      uv run python db/seed/corpus/fixture_stream.py

The seeded catalogue has always pointed its owned rows at a public reference
stream, because there was no real media and a placeholder was honest. The
placeholder being *somebody else's* turned out to be the problem: a viewer whose
network cannot reach that host sees a black player, and nothing about the
platform can fix it. Two different third-party streams have now failed this way
— the first served CORS headers inconsistently per edge, the second is simply
unreachable from some networks.

So the placeholder moves into our own bucket. It is still a placeholder — one
clip standing in for twenty-two talks, with durations that do not match the
metadata — and that is unchanged and still recorded in the README. What changes
is that it is reachable exactly when the rest of the platform is, and its CORS
is the CORS we already verified.

Idempotent. Re-running re-points the rows and skips the upload if the tree is
already there.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).parents[3] / "services" / "pipeline"))

DATABASE_URL = os.environ.get("DATABASE_URL", "")
MEDIA_URL = os.environ.get("MEDIA_SERVICE_URL", "http://127.0.0.1:8899")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")

#: A fixed id, so the tree has one home and re-running does not accumulate
#: copies. Not a real video row — nothing references it as a video.
FIXTURE_ID = "00000000-0000-4000-f000-000000000001"
PREFIX = f"videos/{FIXTURE_ID}/hls"

#: Ten minutes, roughly matching what the borrowed stream was, so the seeded
#: durations are no more wrong than they already were.
SECONDS = 600


async def sign(client: httpx.AsyncClient, key: str, method: str) -> str:
    response = await client.post(
        f"{MEDIA_URL}/v1/internal/sign",
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        json={"key": key, "method": method, "expires_in": 3600},
    )
    response.raise_for_status()
    return response.json()["url"]


async def already_there(client: httpx.AsyncClient) -> bool:
    url = await sign(client, f"{PREFIX}/master.m3u8", "GET")
    return (await client.head(url)).status_code == 200


def render(workspace: Path) -> Path:
    """One 360p rendition. A placeholder does not need a ladder."""
    out = workspace / "hls"
    (out / "360p").mkdir(parents=True)

    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=15:duration={SECONDS}",
            "-f", "lavfi", "-i", f"sine=frequency=220:duration={SECONDS}",
            "-c:v", "libx264", "-preset", "veryfast", "-b:v", "500k",
            "-g", "90", "-keyint_min", "90", "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", "64k", "-ac", "2",
            "-f", "hls", "-hls_time", "6", "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(out / "360p" / "seg-%05d.ts"),
            str(out / "360p" / "index.m3u8"),
        ],
        check=True,
    )

    (out / "master.m3u8").write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=564000,RESOLUTION=640x360\n"
        "360p/index.m3u8\n"
    )
    return out


async def upload(client: httpx.AsyncClient, root: Path) -> int:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    playlists = [p for p in files if p.suffix == ".m3u8"]
    segments = [p for p in files if p not in set(playlists)]

    semaphore = asyncio.Semaphore(6)

    async def send(path: Path) -> None:
        key = f"{PREFIX}/{path.relative_to(root).as_posix()}"
        kind = (
            "application/vnd.apple.mpegurl"
            if path.suffix == ".m3u8"
            else "video/mp2t"
        )
        async with semaphore:
            for attempt in range(3):
                try:
                    url = await sign(client, key, "PUT")
                    response = await client.put(
                        url, content=path.read_bytes(), headers={"Content-Type": kind}
                    )
                    response.raise_for_status()
                    return
                except (httpx.HTTPError, httpx.StreamError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 * (attempt + 1))

    # Segments first: a playlist that lands early describes files that are not
    # there yet.
    for batch in (segments, playlists):
        await asyncio.gather(*(send(path) for path in batch))

    return len(files)


async def main() -> int:
    if not DATABASE_URL or not INTERNAL_TOKEN:
        print("DATABASE_URL and INTERNAL_TOKEN are both required.")
        return 2

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, write=300)) as client:
        if await already_there(client):
            print(f"  fixture stream already in the bucket at {PREFIX}")
        else:
            with tempfile.TemporaryDirectory(prefix="loupe-fixture-") as directory:
                print(f"  rendering {SECONDS}s of placeholder…", flush=True)
                root = render(Path(directory))
                count = await upload(client, root)
                print(f"  uploaded {count} objects to {PREFIX}")

    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=1, max_size=2, statement_cache_size=0
    )
    async with pool.acquire() as connection:
        moved = await connection.fetchval(
            """
            UPDATE video_assets SET hls_url = $1
            WHERE provider = 'demo' OR hls_url LIKE 'http%'
            RETURNING (SELECT count(*) FROM video_assets WHERE hls_url = $1)
            """,
            f"{PREFIX}/master.m3u8",
        )
    await pool.close()

    print(f"  {moved or 0} row(s) now point at media this project hosts")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
