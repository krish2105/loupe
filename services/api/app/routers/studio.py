from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..auth import require_user_id

"""
Creating things, as opposed to reading them.

Everything else in this API answers questions about a catalogue that already
exists. This is where a row starts, and it exists because the upload flow could
not be finished without it: the media service issues a ticket against a video
id, and until now nothing could produce one. The page generated a random UUID
and met a foreign key violation, which is the correct outcome for asking a
database to attach media to a video that was never created.

§5 boundaries hold. This writes `videos` and `channels`, which the core API
owns; the media service still writes only `video_assets` and the transcode
portion of `processing_status`. Neither reaches into the other's columns.
"""

router = APIRouter(prefix="/v1", tags=["studio"])


class NewVideo(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class CreatedVideo(BaseModel):
    id: UUID
    channel_handle: str
    visibility: str
    processing_status: str


def channel_handle_for(user_handle: str) -> str:
    """
    A channel handle derived from the person's own.

    Derived rather than asked for, because a handle prompt at upload time is a
    question with no good answer available yet — someone uploading their first
    talk has not decided what to call a channel, and making them decide is the
    kind of friction that ends an upload. It is editable later, which is where
    the decision actually belongs.

    Reduced to what a handle may contain, and never empty: a user handle of
    entirely punctuation would otherwise produce a channel at `/c/`.
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", user_handle.lower()).strip("-")
    return slug or "channel"


async def _ensure_channel(connection, user_id: UUID) -> tuple[UUID, str]:
    """
    The caller's channel, created on first upload.

    One per person — 0013 enforces that with a partial unique index, so this
    cannot quietly create a second one even if called concurrently.

    The handle needs a suffix when the derived one is taken, and the loop is
    bounded rather than open: a handle that cannot be found in a few tries means
    something is wrong that another attempt will not fix, and an unbounded loop
    against a unique index is how a request hangs instead of failing.
    """
    existing = await connection.fetchrow(
        "SELECT id, handle FROM channels WHERE owner_id = $1", user_id
    )
    if existing is not None:
        return existing["id"], existing["handle"]

    user = await connection.fetchrow(
        "SELECT handle, display_name FROM users WHERE id = $1", user_id
    )
    if user is None:
        # The token verified, so the account exists upstream; the local profile
        # row is what is missing. That is a real state — a first request from a
        # newly confirmed account — and it is not this endpoint's to repair.
        raise HTTPException(
            status_code=409,
            detail="Your profile has not finished setting up. Reload and try again.",
        )

    base = channel_handle_for(user["handle"])

    for attempt in range(8):
        handle = base if attempt == 0 else f"{base}-{attempt + 1}"
        row = await connection.fetchrow(
            """
            INSERT INTO channels (handle, name, source_class, owner_id)
            VALUES ($1, $2, 'owned', $3)
            ON CONFLICT (handle) DO NOTHING
            RETURNING id, handle
            """,
            handle,
            user["display_name"],
            user_id,
        )
        if row is not None:
            return row["id"], row["handle"]

    raise HTTPException(
        status_code=409,
        detail="Could not find a free channel handle. Pick one in your profile.",
    )


@router.post("/videos", response_model=CreatedVideo, status_code=201)
async def create_video(
    request: NewVideo,
    user_id: UUID = Depends(require_user_id),
) -> CreatedVideo:
    """
    Start a video, before there is any media for it.

    Private, always. A row created here has nothing behind it yet — the upload
    has not happened, let alone the transcode — so anything else would put an
    unplayable entry in a public feed. Publishing is a separate act, and making
    it separate is also what gives someone a chance to change their mind about a
    file they have just spent ten minutes uploading.

    `uploaded` is the first stage of the §10.1 machine and means exactly what it
    says here: a record exists, bytes do not.
    """
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    async with pool.acquire() as connection:
        async with connection.transaction():
            channel_id, handle = await _ensure_channel(connection, user_id)

            row = await connection.fetchrow(
                """
                INSERT INTO videos
                  (source_class, channel_id, title, description,
                   processing_status, visibility)
                VALUES ('owned', $1, $2, $3, 'uploaded', 'private')
                RETURNING id, visibility::text, processing_status::text
                """,
                channel_id,
                request.title.strip(),
                (request.description or "").strip() or None,
            )

    return CreatedVideo(
        id=row["id"],
        channel_handle=handle,
        visibility=row["visibility"],
        processing_status=row["processing_status"],
    )
