from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import db
from ..auth import require_user_id

"""
Comments. One reply level only (§6.2).

The depth limit is enforced by a database trigger, so this router does not
re-check it — it translates the resulting error into an HTTP status. Validating
in two places is how the two copies drift.
"""

router = APIRouter(prefix="/v1", tags=["comments"])


class NewComment(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    parent_id: UUID | None = None

    @field_validator("body")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        """
        min_length counts characters, so "   " passes it and then trips the
        database CHECK — which surfaces as a 500 rather than a validation
        error. Strip here so the rejection happens where it can be explained.
        """
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Write something before posting.")
        return cleaned


def require_pool():
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return pool


@router.get("/videos/{video_id}/comments")
async def list_comments(video_id: UUID) -> dict[str, object]:
    """
    Top-level comments, each with its replies.

    One query, assembled in memory. With a one-level limit the reply count per
    thread is small, and a query per thread would be N+1 for no benefit.
    """
    pool = require_pool()

    rows = await pool.fetch(
        """
        SELECT c.id, c.parent_id, c.body, c.created_at, c.edited_at,
               u.id AS author_id, u.handle AS author_handle,
               u.display_name AS author_name, u.avatar_url AS author_avatar
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.video_id = $1
        ORDER BY c.created_at ASC
        """,
        video_id,
    )

    def serialise(row) -> dict:
        return {
            "id": str(row["id"]),
            "body": row["body"],
            "created_at": row["created_at"].isoformat(),
            "edited_at": row["edited_at"].isoformat() if row["edited_at"] else None,
            "author": {
                "id": str(row["author_id"]),
                "handle": row["author_handle"],
                "display_name": row["author_name"],
                "avatar_url": row["author_avatar"],
            },
            "replies": [],
        }

    threads: dict[str, dict] = {}
    orphaned_replies: list = []

    for row in rows:
        node = serialise(row)
        if row["parent_id"] is None:
            threads[str(row["id"])] = node
        else:
            parent = threads.get(str(row["parent_id"]))
            if parent is None:
                orphaned_replies.append(node)
            else:
                parent["replies"].append(node)

    # Newest threads first, but replies stay oldest-first inside a thread —
    # a conversation reads forwards.
    items = sorted(threads.values(), key=lambda n: n["created_at"], reverse=True)

    return {"items": items, "orphaned": len(orphaned_replies)}


@router.post("/videos/{video_id}/comments", status_code=201)
async def create_comment(
    video_id: UUID,
    comment: NewComment,
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    pool = require_pool()

    try:
        row = await pool.fetchrow(
            """
            INSERT INTO comments (video_id, user_id, parent_id, body)
            VALUES ($1, $2, $3, $4)
            RETURNING id, created_at
            """,
            video_id,
            user_id,
            comment.parent_id,
            comment.body,
        )
    except Exception as error:
        message = str(error).lower()
        if "one reply level" in message:
            raise HTTPException(
                status_code=422,
                detail="Replies go one level deep. Reply to the original comment instead.",
            ) from error
        if "foreign key" in message:
            raise HTTPException(status_code=404, detail="No such talk.") from error
        raise

    # §6.1: denormalised counters, updated asynchronously — but a comment count
    # that lags its own comment is the one case people notice immediately.
    await pool.execute(
        """
        INSERT INTO video_stats (video_id, comment_count) VALUES ($1, 1)
        ON CONFLICT (video_id) DO UPDATE
        SET comment_count = video_stats.comment_count + 1, updated_at = now()
        """,
        video_id,
    )

    return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}
