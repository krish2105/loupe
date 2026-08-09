from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path

import httpx

from .config import settings
from .stages import StepFailed

"""
Getting the source out of the bucket and the renditions back in.

The transcoder holds no provider credentials. It asks the media service to sign
each URL, which is the only arrangement that keeps §5's "sole holder of media
provider credentials" true — the alternatives were to copy the keys into a
second service, or to import the signing code and either duplicate SigV4 or add
a path dependency between two packages that both export a top-level `app`.

Asking costs one small round trip per object and buys a real property: rotating
the bucket key touches one service, and a compromised transcoder can mint URLs
only while it can still reach the signer.
"""

logger = logging.getLogger("pipeline.media")

#: An HLS tree is a few hundred small files. One at a time is slow; the target
#: is a laptop or a two-core VM on a domestic connection, so this is enough
#: concurrency to matter and not enough to saturate either.
UPLOAD_CONCURRENCY = 6


async def _sign(client: httpx.AsyncClient, key: str, method: str, ttl: int) -> str:
    if not settings.media_service_url or not settings.internal_token:
        raise StepFailed(
            "the transcoder cannot sign bucket requests. Set MEDIA_SERVICE_URL "
            "and INTERNAL_TOKEN to the media service's address and shared secret."
        )

    response = await client.post(
        f"{settings.media_service_url.rstrip('/')}/v1/internal/sign",
        headers={"Authorization": f"Bearer {settings.internal_token}"},
        json={"key": key, "method": method, "expires_in": ttl},
    )

    if response.status_code == 401:
        raise StepFailed("the media service rejected INTERNAL_TOKEN.")
    if response.status_code >= 400:
        raise StepFailed(
            f"the media service would not sign {key}: {response.status_code}"
        )

    return response.json()["url"]


async def download(key: str, destination: Path) -> None:
    """
    Stream an object to disk.

    Streamed rather than read whole: a two-hour talk is gigabytes and the
    machine this targets has twelve of them for everything.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300)) as client:
        url = await _sign(client, key, "GET", 3600)

        async with client.stream("GET", url) as response:
            if response.status_code == 404:
                raise StepFailed(f"no source object at {key}")
            if response.status_code >= 400:
                raise StepFailed(f"bucket answered {response.status_code} for {key}")

            with destination.open("wb") as handle:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    handle.write(chunk)


async def upload_tree(root: Path, prefix: str) -> int:
    """
    Send a directory to the bucket, preserving its shape.

    Playlists go last, deliberately. A playlist that lands before its segments
    describes files that are not there yet, and anything reading during that
    window gets a 404 per segment. Uploading them last means the tree appears
    complete or not at all.
    """
    files = sorted(path for path in root.rglob("*") if path.is_file())
    playlists = [path for path in files if path.suffix in {".m3u8", ".m3u"}]
    segments = [path for path in files if path not in set(playlists)]

    semaphore = asyncio.Semaphore(UPLOAD_CONCURRENCY)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, write=300)) as client:

        async def send(path: Path) -> None:
            key = f"{prefix}/{path.relative_to(root).as_posix()}"
            content_type = (
                "application/vnd.apple.mpegurl"
                if path.suffix in {".m3u8", ".m3u"}
                else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )

            async with semaphore:
                url = await _sign(client, key, "PUT", 3600)
                response = await client.put(
                    url,
                    content=path.read_bytes(),
                    headers={"Content-Type": content_type},
                )

            if response.status_code >= 400:
                raise StepFailed(f"bucket refused {key} with {response.status_code}")

        for batch in (segments, playlists):
            if batch:
                await asyncio.gather(*(send(path) for path in batch))

    logger.info("uploaded %d objects to %s", len(files), prefix)
    return len(files)
