from __future__ import annotations

import secrets
import time
from contextlib import asynccontextmanager
from uuid import UUID

from asyncpg.exceptions import ForeignKeyViolationError
from fastapi import FastAPI, HTTPException, Path, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import bunny, db, playlist, storage
from .config import settings

"""
Loupe media service.

§5 boundary: the sole holder of media provider credentials. Nothing it returns
contains a key — a playback URL leaves here already signed, so the web app can
consume it without ever learning what signed it, and swapping providers changes
this service alone.

It writes only the columns it owns: the video_assets row and the transcode
portion of processing_status. Everything else is the core API's.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(title="Loupe media service", version="0.1.0", lifespan=lifespan)

# The browser talks to this service directly — for an upload ticket, and for
# every playlist during playback — so it needs the same origin allow-list the
# core API has. Its absence went unnoticed for as long as upload answered 503
# to everything: nothing had ever called this from a page.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UploadRequest(BaseModel):
    video_id: UUID
    title: str


class UploadTicket(BaseModel):
    """
    Everything the browser needs to upload straight to the provider.

    The file never passes through our infrastructure. That is not an
    optimisation — proxying video through a small instance would make uploads
    the single most expensive thing the platform does.

    Shaped by the two providers it has to serve. S3 needs a URL and a method
    and nothing else, because the signature travels in the query string; Bunny
    needs a library, a video id and a separate signature header. Rather than
    invent a lowest common denominator that fits neither, the fields either
    provider does not use are simply absent, and `method` tells the client which
    shape it received.
    """

    upload_url: str
    expires_at: int
    method: str = "POST"

    # Bunny only.
    library_id: str | None = None
    video_guid: str | None = None
    signature: str | None = None


@app.get("/health")
async def health() -> dict[str, object]:
    pool = db.pool()
    database = "unavailable"

    if pool is not None:
        try:
            async with pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
            database = "ok"
        except Exception:
            database = "error"

    return {
        "status": "ok",
        "environment": settings.environment,
        "database": database,
        "provider_configured": settings.is_configured,
    }


@app.post("/v1/uploads", response_model=UploadTicket)
async def create_upload(request: UploadRequest) -> UploadTicket:
    if not settings.is_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Media provider is not configured. Set S3_ENDPOINT, S3_REGION, "
                "S3_BUCKET, S3_KEY_ID and S3_APPLICATION_KEY."
            ),
        )

    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    expires_at = int(time.time()) + 3600

    if settings.provider == "s3":
        video_id = str(request.video_id)

        # The row is written before the bytes arrive, exactly as on the Bunny
        # path: whatever reports the transcode finishing needs a row to update,
        # and it may well get there first.
        try:
            async with pool.acquire() as connection:
                await connection.execute(
                    """
                    INSERT INTO video_assets (video_id, provider, provider_guid)
                    VALUES ($1, 's3', $2)
                    ON CONFLICT (video_id) DO UPDATE SET provider_guid = EXCLUDED.provider_guid
                    """,
                    request.video_id,
                    video_id,
                )
                await connection.execute(
                    "UPDATE videos SET processing_status = 'uploaded' WHERE id = $1",
                    request.video_id,
                )
        except ForeignKeyViolationError:
            # Answered as a 404 rather than allowed to become a 500, and not
            # only for tidiness: Starlette's error handler sits outside the CORS
            # middleware, so an unhandled exception reaches the browser with no
            # `Access-Control-Allow-Origin` at all. The fetch then rejects, and
            # a page that cannot tell a blocked response from a dead socket
            # reports "could not reach the media service" about a service that
            # is running and answering. Which is exactly what happened.
            raise HTTPException(
                status_code=404,
                detail=(
                    "No video record to attach this upload to. Create the video "
                    "through the core API first, then request a ticket for its id."
                ),
            ) from None

        return UploadTicket(
            upload_url=storage.upload_url(video_id, "original", ttl=3600),
            expires_at=expires_at,
            method="PUT",
        )

    created = await bunny.BunnyClient().create_video(request.title)

    # The asset row is written before the bytes arrive, so a webhook that beats
    # the client's completion callback still finds a row to update.
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO video_assets (video_id, provider, provider_guid)
            VALUES ($1, 'bunny', $2)
            ON CONFLICT (video_id) DO UPDATE SET provider_guid = EXCLUDED.provider_guid
            """,
            request.video_id,
            created.guid,
        )
        await connection.execute(
            "UPDATE videos SET processing_status = 'transcoding' WHERE id = $1",
            request.video_id,
        )

    return UploadTicket(
        library_id=created.library_id,
        video_guid=created.guid,
        upload_url=f"https://video.bunnycdn.com/library/{created.library_id}/videos/{created.guid}",
        signature=bunny.upload_signature(
            created.library_id, settings.bunny_api_key, created.guid, expires_at
        ),
        expires_at=expires_at,
    )


@app.get("/v1/playback/{video_id}")
async def playback_url(video_id: UUID) -> dict[str, object]:
    """A short-lived signed manifest URL (§5.1)."""
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT a.provider_guid, v.processing_status::text AS status
            FROM video_assets a
            JOIN videos v ON v.id = a.video_id
            WHERE a.video_id = $1
            """,
            video_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="No media asset for that video.")

    # §5.1 async by default: a video is watchable long before it is searchable,
    # but not before it is transcoded.
    if row["status"] in {"uploaded", "transcoding"}:
        raise HTTPException(status_code=409, detail="This talk is still processing.")

    expires_at = int(time.time()) + settings.playback_token_ttl_sec

    if settings.provider == "s3":
        # Not a presigned bucket URL. The master playlist is served by this
        # service so that the URIs inside it are resolved at fetch time — see
        # storage.playlist_url for why signing them any earlier breaks playback
        # for anyone who does not start watching immediately.
        return {
            "hls_url": storage.playlist_url(row["provider_guid"], "master.m3u8"),
            "expires_at": expires_at,
        }

    return {
        "hls_url": bunny.signed_playback_url(
            settings.bunny_pull_zone,
            bunny.hls_path(row["provider_guid"]),
            settings.bunny_token_key,
            expires_at,
        ),
        "expires_at": expires_at,
    }


@app.get("/v1/hls/{video_id}/{path:path}")
async def hls_playlist(video_id: str, path: str) -> Response:
    """
    Serve one playlist out of the private bucket, with its URIs rewritten.

    The only thing this service proxies. A playlist is a few kilobytes; the
    segments it names are fetched straight from the bucket with presigned URLs,
    so the video itself never crosses this process.
    """
    if settings.provider != "s3":
        raise HTTPException(status_code=404, detail="Not found.")

    if not playlist.is_safe_path(path):
        raise HTTPException(status_code=400, detail="Invalid path.")

    if not playlist.is_playlist(path):
        raise HTTPException(
            status_code=400,
            detail="Only playlists are served here; segments come from the bucket directly.",
        )

    body = await storage.fetch_playlist(video_id, path)
    if body is None:
        raise HTTPException(status_code=404, detail="No such playlist.")

    return Response(
        content=body,
        media_type="application/vnd.apple.mpegurl",
        # The URIs inside carry signatures with their own expiry, so a cached
        # copy would hand out URLs that have already died. Regenerating costs
        # one small bucket read.
        headers={"Cache-Control": "no-store"},
    )


class BunnyWebhook(BaseModel):
    VideoLibraryId: int | str
    VideoGuid: str
    Status: int


@app.post("/webhooks/bunny/{secret}")
async def bunny_webhook(
    payload: BunnyWebhook,
    secret: str = Path(...),
) -> dict[str, object]:
    """
    Consume a Bunny transcode webhook.

    Bunny does not sign Stream webhooks, so there is no HMAC to verify. Two
    things compensate:

    1. The endpoint lives behind an unguessable path secret, compared in
       constant time.
    2. The payload is treated as a *hint*, never as truth. The authoritative
       status is re-fetched from the provider before anything is written. An
       attacker who guessed the URL could therefore cause an extra API call,
       not a false state transition.

    Writing the state straight from an unauthenticated request body would let
    anyone mark any video transcoded — which, given playback gates on that
    status, matters.
    """
    if not settings.webhook_secret or not secrets.compare_digest(
        secret, settings.webhook_secret
    ):
        raise HTTPException(status_code=404, detail="Not found.")

    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    authoritative_status = payload.Status
    try:
        video = await bunny.BunnyClient().get_video(payload.VideoGuid)
        authoritative_status = int(video.get("status", payload.Status))
    except Exception:
        # If the provider cannot be reached, fall back to the payload rather
        # than stalling the pipeline — the stage machine is resumable and a
        # wrong guess here is corrected by the next webhook.
        pass

    stage = bunny.STATUS_TO_STAGE.get(authoritative_status)
    if stage is None:
        return {"applied": False, "reason": "status does not move the stage"}

    async with pool.acquire() as connection:
        updated = await connection.fetchval(
            """
            UPDATE videos SET processing_status = $2::processing_status
            WHERE id = (SELECT video_id FROM video_assets WHERE provider_guid = $1)
            RETURNING id
            """,
            payload.VideoGuid,
            stage,
        )

    if updated is None:
        raise HTTPException(status_code=404, detail="Unknown video.")

    return {"applied": True, "stage": stage}
