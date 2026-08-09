"""
Bunny Stream integration.

The two signing functions are pure and separately testable, which matters: a
signature that is subtly wrong fails as a 403 from a CDN edge, with no useful
error, usually only in production. Testing them against known vectors is
cheaper than debugging that.

Provider choice and the alternatives considered are in docs/adr/0001.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from enum import IntEnum

import httpx

from .config import settings

BUNNY_API_BASE = "https://video.bunnycdn.com/library"


class BunnyStatus(IntEnum):
    """Status values Bunny sends on its webhook."""

    QUEUED = 0
    PROCESSING = 1
    ENCODING = 2
    FINISHED = 3
    RESOLUTION_FINISHED = 4
    FAILED = 5
    PRESIGNED_UPLOAD_STARTED = 6
    PRESIGNED_UPLOAD_FINISHED = 7
    PRESIGNED_UPLOAD_FAILED = 8
    CAPTIONS_GENERATED = 9
    TITLE_OR_DESCRIPTION_UPDATED = 10


# Bunny's vocabulary mapped onto the §10.1 stage machine. Statuses absent from
# this map are real events that do not move the stage — a resolution finishing
# is progress within encoding, not a transition out of it.
STATUS_TO_STAGE: dict[int, str] = {
    BunnyStatus.QUEUED: "transcoding",
    BunnyStatus.PROCESSING: "transcoding",
    BunnyStatus.ENCODING: "transcoding",
    BunnyStatus.FINISHED: "transcoded",
    BunnyStatus.FAILED: "failed_transcoding",
    BunnyStatus.PRESIGNED_UPLOAD_FAILED: "failed_transcoding",
}


def upload_signature(
    library_id: str, api_key: str, video_id: str, expires_at: int
) -> str:
    """
    Signature for a presigned (TUS) upload.

    Bunny specifies sha256(library_id + api_key + expiration + video_id) as hex.
    Handing this to the browser lets the file go straight to Bunny — the API
    host never proxies video bytes, which is the only reason a $7 instance can
    serve uploads at all.
    """
    payload = f"{library_id}{api_key}{expires_at}{video_id}"
    return hashlib.sha256(payload.encode()).hexdigest()


def signed_playback_url(
    pull_zone: str,
    path: str,
    token_key: str,
    expires_at: int,
) -> str:
    """
    A CDN token-authenticated playback URL (§5.1).

    Bunny's scheme: base64(raw sha256(token_key + path + expires)), then made
    URL-safe by mapping +/ to -_ and dropping the padding. Getting any of those
    three steps wrong yields a 403 at the edge and nothing else.

    Signed even for openly licensed content, because the cost is zero and the
    alternative is a permanent public URL to every asset in the library.
    """
    if not path.startswith("/"):
        path = f"/{path}"

    digest = hashlib.sha256(f"{token_key}{path}{expires_at}".encode()).digest()
    token = (
        base64.b64encode(digest)
        .decode()
        .replace("\n", "")
        .replace("+", "-")
        .replace("/", "_")
        .replace("=", "")
    )
    return f"https://{pull_zone}{path}?token={token}&expires={expires_at}"


def hls_path(video_guid: str) -> str:
    return f"/{video_guid}/playlist.m3u8"


def thumbnail_sprite_path(video_guid: str) -> str:
    return f"/{video_guid}/preview.webp"


@dataclass(frozen=True)
class CreatedVideo:
    guid: str
    library_id: str


class BunnyClient:
    """Management API calls. Playback signing needs no network round-trip."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {
            "AccessKey": settings.bunny_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=15) as client:
            return await client.request(method, url, **kwargs)

    async def create_video(self, title: str) -> CreatedVideo:
        url = f"{BUNNY_API_BASE}/{settings.bunny_library_id}/videos"
        response = await self._request(
            "POST", url, headers=self._headers(), json={"title": title}
        )
        response.raise_for_status()
        return CreatedVideo(
            guid=response.json()["guid"], library_id=settings.bunny_library_id
        )

    async def get_video(self, video_guid: str) -> dict:
        """
        Authoritative state for a video.

        Used to re-check the status after a webhook arrives rather than
        believing the payload — see main.py.
        """
        url = f"{BUNNY_API_BASE}/{settings.bunny_library_id}/videos/{video_guid}"
        response = await self._request("GET", url, headers=self._headers())
        response.raise_for_status()
        return response.json()
