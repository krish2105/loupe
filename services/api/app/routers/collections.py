from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..auth import require_user_id
from .catalogue import VIDEO_COLUMNS, serialise

"""
The shared collection abstraction — §6.2.

    "The four 'list' surfaces are one abstraction with different semantics.
     Build the abstraction once; get four surfaces."

The insight is that Subscriptions, History, Watch Later, and Playlists are all
the same thing: *a user-scoped set of videos, with a membership rule and an
ordering*. Only those two vary. Everything downstream — the join to video
columns, the capability flags, the serialisation, the visibility filter, the
pagination — is identical, and writing it four times is how four surfaces
quietly drift apart.

So a collection is declared, not implemented. Adding a fifth surface later means
adding a row to COLLECTIONS, not writing another endpoint.

The Phase 3 gate is explicit that four one-offs do not pass.
"""

router = APIRouter(prefix="/v1/me", tags=["collections"])


@dataclass(frozen=True)
class Collection:
    key: str
    title: str
    #: Written to the §7.6 standard: an empty screen is an invitation to act.
    empty_title: str
    empty_body: str
    #: Produces (video_id, sort_key, context). $1 is always the user id.
    membership_sql: str
    #: Descending is right for every current surface; kept explicit rather than
    #: assumed, because "oldest first" is a plausible future playlist ordering.
    descending: bool = True


COLLECTIONS: dict[str, Collection] = {
    "history": Collection(
        key="history",
        title="History",
        empty_title="Nothing watched yet",
        empty_body=(
            "Talks you watch appear here, most recent first, "
            "so you can pick any of them back up."
        ),
        # DISTINCT ON collapses the append-only log to one row per video (§6.5):
        # the position is a read-side aggregate, never a stored column.
        membership_sql="""
            SELECT DISTINCT ON (w.video_id)
                   w.video_id,
                   w.occurred_at AS sort_key,
                   jsonb_build_object(
                     'position_sec', w.position_sec,
                     'watch_pct', w.watch_pct,
                     'completed', w.completed
                   ) AS context
            FROM watch_events w
            WHERE w.user_id = $1
            ORDER BY w.video_id, w.occurred_at DESC
        """,
    ),
    "watch_later": Collection(
        key="watch_later",
        title="Watch later",
        empty_title="Nothing saved yet",
        empty_body=(
            "Save a talk from its page and it waits here until you have time for it."
        ),
        membership_sql="""
            SELECT si.video_id, si.added_at AS sort_key, '{}'::jsonb AS context
            FROM saved_items si
            WHERE si.user_id = $1 AND si.list_type = 'watch_later'
        """,
    ),
    "liked": Collection(
        key="liked",
        title="Liked",
        empty_title="Nothing liked yet",
        empty_body="Talks you like are collected here.",
        membership_sql="""
            SELECT si.video_id, si.added_at AS sort_key, '{}'::jsonb AS context
            FROM saved_items si
            WHERE si.user_id = $1 AND si.list_type = 'liked'
        """,
    ),
    "subscriptions": Collection(
        key="subscriptions",
        title="Subscriptions",
        empty_title="No subscriptions yet",
        empty_body="Follow a channel and its new talks land here.",
        # Subscriptions is a channel relationship, but the *surface* is a video
        # feed — which is exactly why it belongs in this abstraction rather than
        # being its own endpoint.
        membership_sql="""
            SELECT v2.id AS video_id, v2.published_at AS sort_key, '{}'::jsonb AS context
            FROM subscriptions sub
            JOIN videos v2 ON v2.channel_id = sub.channel_id
            WHERE sub.user_id = $1
        """,
    ),
}


def require_pool():
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return pool


async def load_collection(
    pool,
    membership_sql: str,
    params: list,
    limit: int,
    descending: bool = True,
) -> list[dict]:
    """
    The one query every collection surface runs.

    Membership varies; everything after it does not. Video columns, capability
    flags, visibility, and ordering are shared, so a change to the capability
    matrix reaches all four surfaces at once instead of three of them.
    """
    direction = "DESC" if descending else "ASC"
    limit_placeholder = f"${len(params) + 1}"

    rows = await pool.fetch(
        f"""
        WITH membership AS ({membership_sql})
        SELECT {VIDEO_COLUMNS}, m.context
        FROM membership m
        JOIN videos v ON v.id = m.video_id
        JOIN channels c ON c.id = v.channel_id
        LEFT JOIN video_stats s ON s.video_id = v.id
        WHERE v.visibility = 'public'
        ORDER BY m.sort_key {direction} NULLS LAST
        LIMIT {limit_placeholder}
        """,
        *params,
        limit,
    )

    items = []
    for row in rows:
        payload = serialise(row)
        # asyncpg hands back jsonb as text unless a codec is registered, so the
        # history position would otherwise reach the client as a string that
        # merely looks like an object.
        context = row["context"]
        if isinstance(context, str):
            context = json.loads(context)
        if context:
            payload["context"] = context
        items.append(payload)
    return items


@router.get("/collections/{key}")
async def collection(
    key: str,
    limit: int = Query(48, ge=1, le=100),
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    spec = COLLECTIONS.get(key)
    if spec is None:
        raise HTTPException(status_code=404, detail="No such collection.")

    pool = require_pool()
    items = await load_collection(
        pool, spec.membership_sql, [user_id], limit, spec.descending
    )

    return {
        "key": spec.key,
        "title": spec.title,
        "empty_title": spec.empty_title,
        "empty_body": spec.empty_body,
        "items": items,
    }


@router.get("/collections")
async def list_collections(
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    """
    What collections exist, and how full each one is.

    One round-trip for the counts, so a nav badge does not become four requests.
    """
    pool = require_pool()

    counts = await pool.fetchrow(
        """
        SELECT
          (SELECT count(DISTINCT video_id) FROM watch_events
           WHERE user_id = $1) AS history,
          (SELECT count(*) FROM saved_items
           WHERE user_id = $1 AND list_type = 'watch_later') AS watch_later,
          (SELECT count(*) FROM saved_items
           WHERE user_id = $1 AND list_type = 'liked') AS liked,
          (SELECT count(*) FROM subscriptions WHERE user_id = $1) AS subscriptions,
          (SELECT count(*) FROM playlists WHERE owner_id = $1) AS playlists
        """,
        user_id,
    )

    return {
        "collections": [
            {"key": spec.key, "title": spec.title, "count": counts[spec.key]}
            for spec in COLLECTIONS.values()
        ],
        "playlist_count": counts["playlists"],
    }


# --------------------------------------------------------------- membership ---
# Adds are idempotent PUTs rather than POSTs: clicking Save twice is a thing
# people do, and the second click should be a no-op rather than an error.

SAVED_LISTS = {"watch_later", "liked"}


@router.put("/subscriptions/{channel_id}", status_code=204)
async def subscribe(channel_id: UUID, user_id: UUID = Depends(require_user_id)) -> None:
    pool = require_pool()
    try:
        await pool.execute(
            """
            INSERT INTO subscriptions (user_id, channel_id) VALUES ($1, $2)
            ON CONFLICT (user_id, channel_id) DO NOTHING
            """,
            user_id,
            channel_id,
        )
    except Exception as error:
        if "foreign key" in str(error).lower():
            raise HTTPException(status_code=404, detail="No such channel.") from error
        raise


@router.delete("/subscriptions/{channel_id}", status_code=204)
async def unsubscribe(channel_id: UUID, user_id: UUID = Depends(require_user_id)) -> None:
    pool = require_pool()
    await pool.execute(
        "DELETE FROM subscriptions WHERE user_id = $1 AND channel_id = $2",
        user_id,
        channel_id,
    )


@router.put("/saved/{list_type}/{video_id}", status_code=204)
async def save_video(
    list_type: str, video_id: UUID, user_id: UUID = Depends(require_user_id)
) -> None:
    if list_type not in SAVED_LISTS:
        raise HTTPException(status_code=404, detail="No such list.")

    pool = require_pool()
    try:
        await pool.execute(
            """
            INSERT INTO saved_items (user_id, video_id, list_type)
            VALUES ($1, $2, $3::saved_list_type)
            ON CONFLICT (user_id, video_id, list_type) DO NOTHING
            """,
            user_id,
            video_id,
            list_type,
        )
    except Exception as error:
        if "foreign key" in str(error).lower():
            raise HTTPException(status_code=404, detail="No such talk.") from error
        raise


@router.delete("/saved/{list_type}/{video_id}", status_code=204)
async def unsave_video(
    list_type: str, video_id: UUID, user_id: UUID = Depends(require_user_id)
) -> None:
    if list_type not in SAVED_LISTS:
        raise HTTPException(status_code=404, detail="No such list.")

    pool = require_pool()
    await pool.execute(
        """
        DELETE FROM saved_items
        WHERE user_id = $1 AND video_id = $2 AND list_type = $3::saved_list_type
        """,
        user_id,
        video_id,
        list_type,
    )


@router.get("/state/{video_id}")
async def video_state(
    video_id: UUID, user_id: UUID = Depends(require_user_id)
) -> dict[str, object]:
    """
    This person's relationship to one talk.

    One request rather than three, because the video page needs all of it at
    once to render its action bar without three separate spinners.
    """
    pool = require_pool()

    row = await pool.fetchrow(
        """
        SELECT
          EXISTS (SELECT 1 FROM saved_items
                  WHERE user_id = $1 AND video_id = $2
                    AND list_type = 'watch_later') AS watch_later,
          EXISTS (SELECT 1 FROM saved_items
                  WHERE user_id = $1 AND video_id = $2 AND list_type = 'liked') AS liked,
          EXISTS (SELECT 1 FROM subscriptions s
                  JOIN videos v ON v.channel_id = s.channel_id
                  WHERE s.user_id = $1 AND v.id = $2) AS subscribed
        """,
        user_id,
        video_id,
    )

    return {
        "watch_later": row["watch_later"],
        "liked": row["liked"],
        "subscribed": row["subscribed"],
    }


# ---------------------------------------------------------------- playlists ---
# A playlist is the same collection with a different membership rule, so it
# reuses load_collection rather than growing its own query.


@router.get("/playlists")
async def list_playlists(user_id: UUID = Depends(require_user_id)) -> dict[str, object]:
    pool = require_pool()

    rows = await pool.fetch(
        """
        SELECT p.id, p.title, p.description, p.visibility::text AS visibility,
               p.generated_by::text AS generated_by, p.rationale, p.updated_at,
               count(pi.video_id) AS item_count
        FROM playlists p
        LEFT JOIN playlist_items pi ON pi.playlist_id = p.id
        WHERE p.owner_id = $1
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """,
        user_id,
    )

    return {
        "items": [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "description": row["description"],
                "visibility": row["visibility"],
                # §12/§11: an AI-composed playlist carries its written rationale,
                # and the UI must be able to say which is which.
                "generated_by": row["generated_by"],
                "rationale": row["rationale"],
                "item_count": row["item_count"],
            }
            for row in rows
        ]
    }


@router.post("/playlists", status_code=201)
async def create_playlist(
    payload: dict, user_id: UUID = Depends(require_user_id)
) -> dict[str, object]:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=422, detail="Give the playlist a name.")

    pool = require_pool()
    row = await pool.fetchrow(
        "INSERT INTO playlists (owner_id, title) VALUES ($1, $2) RETURNING id",
        user_id,
        title[:200],
    )
    return {"id": str(row["id"])}


@router.get("/playlists/{playlist_id}")
async def playlist_detail(
    playlist_id: UUID,
    limit: int = Query(200, ge=1, le=500),
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    pool = require_pool()

    playlist = await pool.fetchrow(
        """
        SELECT id, title, description, owner_id, visibility::text AS visibility,
               generated_by::text AS generated_by, rationale
        FROM playlists WHERE id = $1
        """,
        playlist_id,
    )

    if playlist is None:
        raise HTTPException(status_code=404, detail="No such playlist.")

    # Someone else's private playlist should be indistinguishable from one that
    # does not exist — a 403 confirms it is real.
    if playlist["owner_id"] != user_id and playlist["visibility"] != "public":
        raise HTTPException(status_code=404, detail="No such playlist.")

    items = await load_collection(
        pool,
        """
        SELECT pi.video_id, pi.position AS sort_key, '{}'::jsonb AS context
        FROM playlist_items pi
        WHERE pi.playlist_id = $1
        """,
        [playlist_id],
        limit,
        descending=False,  # A playlist is an ordering, and it reads forwards.
    )

    return {
        "id": str(playlist["id"]),
        "title": playlist["title"],
        "description": playlist["description"],
        "visibility": playlist["visibility"],
        "generated_by": playlist["generated_by"],
        "rationale": playlist["rationale"],
        "is_owner": playlist["owner_id"] == user_id,
        "items": items,
    }


@router.put("/playlists/{playlist_id}/items/{video_id}", status_code=204)
async def add_to_playlist(
    playlist_id: UUID, video_id: UUID, user_id: UUID = Depends(require_user_id)
) -> None:
    pool = require_pool()

    owner = await pool.fetchval("SELECT owner_id FROM playlists WHERE id = $1", playlist_id)
    if owner is None or owner != user_id:
        raise HTTPException(status_code=404, detail="No such playlist.")

    try:
        await pool.execute(
            """
            INSERT INTO playlist_items (playlist_id, video_id, position)
            VALUES ($1, $2, COALESCE(
                (SELECT max(position) + 1 FROM playlist_items WHERE playlist_id = $1), 0
            ))
            ON CONFLICT (playlist_id, video_id) DO NOTHING
            """,
            playlist_id,
            video_id,
        )
    except Exception as error:
        if "foreign key" in str(error).lower():
            raise HTTPException(status_code=404, detail="No such talk.") from error
        raise


@router.delete("/playlists/{playlist_id}/items/{video_id}", status_code=204)
async def remove_from_playlist(
    playlist_id: UUID, video_id: UUID, user_id: UUID = Depends(require_user_id)
) -> None:
    pool = require_pool()

    owner = await pool.fetchval("SELECT owner_id FROM playlists WHERE id = $1", playlist_id)
    if owner is None or owner != user_id:
        raise HTTPException(status_code=404, detail="No such playlist.")

    await pool.execute(
        "DELETE FROM playlist_items WHERE playlist_id = $1 AND video_id = $2",
        playlist_id,
        video_id,
    )
