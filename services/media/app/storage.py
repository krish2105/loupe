"""
The S3 storage adapter.

Thin on purpose. Everything with a rule in it — the signature, the playlist
rewriting — is a pure function in `s3.py` and `playlist.py` where it can be
tested without a bucket. What is left here is the part that genuinely needs the
network, and it is deliberately small enough to read in one go.

Two things pass through this service and only two: an upload ticket on the way
in, and a playlist on the way out. Video bytes travel browser-to-bucket and
bucket-to-viewer without touching us, which is the only reason a free-tier
instance can serve a video platform at all.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from . import playlist as playlist_module
from . import s3
from .config import settings


class PlaylistUnavailable(RuntimeError):
    """The bucket could not supply a playlist, with the reason attached."""


def _sign(key: str, ttl: int, method: str = "GET") -> str:
    return s3.presigned_url(
        endpoint=settings.s3_endpoint,
        region=settings.s3_region,
        bucket=settings.s3_bucket,
        key=key,
        access_key=settings.s3_key_id,
        secret_key=settings.s3_application_key,
        expires_in=ttl,
        now=datetime.now(UTC),
        method=method,
    )


def sign_key(key: str, ttl: int, method: str = "GET") -> str:
    """Sign an arbitrary key. Used by /v1/internal/sign for the transcoder."""
    return _sign(key, ttl, method=method)


def upload_url(video_id: str, filename: str, ttl: int) -> str:
    """
    A presigned PUT the browser can send the file straight to.

    The original lands beside the HLS output rather than in a separate staging
    bucket, so one prefix still holds everything a takedown has to remove.
    """
    return _sign(f"videos/{video_id}/source/{filename}", ttl, method="PUT")


def segment_url(video_id: str, path: str) -> str:
    """A presigned URL for one segment, fetched by the player directly."""
    return _sign(s3.hls_key(video_id, path), settings.s3_segment_ttl_sec)


def playlist_url(video_id: str, path: str) -> str:
    """
    A URL for a nested playlist, pointing back at this service.

    Nested playlists are not presigned. Signing one now would freeze the
    signatures of every segment it names at the moment the parent was fetched,
    so a viewer who opened a talk and started watching an hour later would meet
    a wall of 403s. Routing it back here means its segments are signed when it
    is actually requested.
    """
    base = settings.public_base_url.rstrip("/")
    return f"{base}/v1/hls/{video_id}/{path.lstrip('/')}"


async def fetch_playlist(video_id: str, path: str) -> str | None:
    """
    Read a playlist out of the bucket and rewrite every URI in it.

    Returns None when the object is absent, which the caller turns into a 404 —
    an unwritten playlist and a wrong path are the same thing from here.
    """
    key = s3.hls_key(video_id, path)
    url = _sign(key, 60)

    try:
        # Generous, because a free instance reaching a bucket across regions on
        # a cold start is slower than anything measured locally.
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, read=30)) as client:
            response = await client.get(url)
    except httpx.HTTPError as error:
        # Otherwise this is a bare 500 with the cause only in a log nobody is
        # tailing. A misconfigured endpoint — a stray space from pasting a
        # value, most likely — looks identical to an outage from outside.
        raise PlaylistUnavailable(
            f"could not reach the bucket for {key}: {type(error).__name__}"
        ) from error

    if response.status_code == 404:
        return None

    if response.status_code >= 400:
        raise PlaylistUnavailable(
            f"the bucket answered {response.status_code} for {key}"
        )

    # A playlist's URIs are relative to the playlist, not to the video root, so
    # a nested one has to resolve its children against its own directory.
    directory = path.rsplit("/", 1)[0] if "/" in path else ""

    def resolve(uri: str) -> str:
        relative = f"{directory}/{uri}" if directory else uri
        if playlist_module.is_playlist(uri):
            return playlist_url(video_id, relative)
        return segment_url(video_id, relative)

    return playlist_module.rewrite(response.text, resolve)
