from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db
from ..auth import require_user_id
from ..config import settings
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
    "downloads": Collection(
        key="downloads",
        title="Downloads",
        empty_title="Nothing downloaded yet",
        empty_body=(
            "Download an episode and it plays without a connection. "
            "Only talks Loupe hosts can be downloaded."
        ),
        # A fifth surface, and it cost a dictionary entry. §6.2 predicted that
        # in Phase 0 and this is the first time it was tested by something the
        # abstraction was not designed against.
        membership_sql="""
            SELECT d.video_id, d.requested_at AS sort_key,
                   jsonb_build_object('bytes', d.bytes) AS context
            FROM downloads d
            WHERE d.user_id = $1
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
          (SELECT count(*) FROM downloads WHERE user_id = $1) AS downloads,
          (SELECT count(*) FROM playlists WHERE owner_id = $1) AS playlists
        """,
        user_id,
    )

    return {
        "collections": [
            {"key": spec.key, "title": spec.title, "count": counts[spec.key]}
            for spec in COLLECTIONS.values()
        ],
        "download_count": counts["downloads"],
        "playlist_count": counts["playlists"],
    }


@router.get("/notifications")
async def notifications(
    limit: int = Query(50, ge=1, le=100),
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    """
    §6.2: fan-out on write, so this is a plain read of one person's rows.

    The rows are written by database triggers (migration 0009) rather than by
    this service, because three different writers create notifiable events — the
    pipeline flipping a talk to transcoded, the nightly ingest worker inserting
    Class B rows, and comment replies — and only the last of those passes
    through here.
    """
    pool = require_pool()

    rows = await pool.fetch(
        """
        SELECT n.id, n.kind::text AS kind, n.target_id, n.created_at, n.read_at,
               v.title AS target_title, c.name AS channel_name, c.handle AS channel_handle,
               a.display_name AS actor_name
        FROM notifications n
        LEFT JOIN videos v ON v.id = n.target_id
        LEFT JOIN channels c ON c.id = v.channel_id
        LEFT JOIN users a ON a.id = n.actor_id
        WHERE n.user_id = $1
        ORDER BY n.created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    # Counted rather than summed over the page. Summing would report at most
    # `limit` for anyone with a backlog, and zero for anyone whose unread rows
    # had already scrolled past it.
    unread = await pool.fetchval(
        "SELECT count(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL",
        user_id,
    )

    return {
        "items": [
            {
                "id": str(row["id"]),
                "kind": row["kind"],
                "target_id": str(row["target_id"]),
                "target_title": row["target_title"],
                "channel_name": row["channel_name"],
                "channel_handle": row["channel_handle"],
                "actor_name": row["actor_name"],
                "created_at": row["created_at"].isoformat(),
                "read": row["read_at"] is not None,
            }
            for row in rows
        ],
        "unread": unread,
    }


@router.post("/notifications/read")
async def mark_notifications_read(
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    """
    Mark everything read, which is what opening the page means.

    Per-item read state was considered and dropped. The only place a
    notification is ever displayed is this page, so recording which individual
    rows were looked at would store a distinction nothing can act on. The unread
    flag stays per row, so anything that arrives while the page is open is still
    marked when it does.
    """
    pool = require_pool()

    marked = await pool.execute(
        "UPDATE notifications SET read_at = now() WHERE user_id = $1 AND read_at IS NULL",
        user_id,
    )

    # asyncpg returns the command tag, e.g. "UPDATE 3".
    return {"marked_read": int(marked.rsplit(" ", 1)[-1])}


@router.get("/channels")
async def subscribed_channels(
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    """
    Channels this person follows, for the sidebar.

    Separate from the subscriptions *collection*, which returns their videos.
    The sidebar wants the channels themselves, and asking for 48 videos to
    derive a list of four channels would be absurd.
    """
    pool = require_pool()

    rows = await pool.fetch(
        """
        SELECT c.id, c.handle, c.name, c.avatar_url, s.notify_enabled
        FROM subscriptions s
        JOIN channels c ON c.id = s.channel_id
        WHERE s.user_id = $1
        ORDER BY c.name
        """,
        user_id,
    )

    return {
        "items": [
            {
                "id": str(row["id"]),
                "handle": row["handle"],
                "name": row["name"],
                "avatar_url": row["avatar_url"],
                "notify_enabled": row["notify_enabled"],
            }
            for row in rows
        ]
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


# ---------------------------------------------------------------- downloads ---
# ADR 0003. The bytes live in the browser's Cache Storage; these rows are the
# record of what was asked for and how big it turned out.


class DownloadRecord(BaseModel):
    #: Written when the transfer finishes. Absent means it was started and never
    #: completed, which is what lets the UI offer a retry rather than showing a
    #: download that does not work.
    bytes: int | None = Field(default=None, ge=0)


@router.put("/downloads/{video_id}", status_code=204)
async def record_download(
    video_id: UUID,
    payload: DownloadRecord,
    user_id: UUID = Depends(require_user_id),
) -> None:
    """
    Record a download, or complete one.

    Called twice per download: once when it starts, with no size, and once when
    it finishes, with the size. Upsert rather than two endpoints, because "start"
    and "finish" are the same fact at different stages of completeness.
    """
    pool = require_pool()

    try:
        await pool.execute(
            """
            INSERT INTO downloads (user_id, video_id, bytes)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, video_id) DO UPDATE
            SET bytes = COALESCE(EXCLUDED.bytes, downloads.bytes)
            """,
            user_id,
            video_id,
            payload.bytes,
        )
    except Exception as error:
        message = str(error).lower()
        # The database refuses Class B downloads (migration 0012). Translated
        # here rather than pre-checked, so there is one rule and not two.
        if "referenced content cannot be downloaded" in message:
            raise HTTPException(
                status_code=409,
                detail="This talk is hosted elsewhere, so it cannot be downloaded.",
            ) from error
        if "foreign key" in message:
            raise HTTPException(status_code=404, detail="No such talk.") from error
        raise


@router.delete("/downloads/{video_id}", status_code=204)
async def remove_download(
    video_id: UUID, user_id: UUID = Depends(require_user_id)
) -> None:
    pool = require_pool()
    await pool.execute(
        "DELETE FROM downloads WHERE user_id = $1 AND video_id = $2",
        user_id,
        video_id,
    )


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
        SELECT pi.video_id, pi.position AS sort_key,
               -- The matched moment rides in `context`, which is what the shared
               -- abstraction provides it for. Stripping nulls means a hand-made
               -- playlist carries no empty keys for the UI to test against.
               jsonb_strip_nulls(jsonb_build_object(
                 'start_sec', pi.start_sec,
                 'note', pi.note
               )) AS context
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


class PlaylistBrief(BaseModel):
    brief: str = Field(min_length=8, max_length=300)
    limit: int = Field(default=8, ge=3, le=12)


@router.post("/playlists/compose", status_code=201)
async def compose_playlist(
    payload: PlaylistBrief, user_id: UUID = Depends(require_user_id)
) -> dict[str, object]:
    """
    §11 AI playlists. A brief in, a real saved playlist out.

    The composition happens in the AI service, which owns every prompt and every
    model call (§5). This service does what it owns: authorising the caller,
    writing the rows, and deciding what a refusal means to a client. Splitting it
    this way is why the AI service never needs to verify a session token.

    A refusal is a 200, not an error. "Nothing in the catalogue covers this well
    enough" is a successful, correct answer to the brief — the same judgement
    ask-video makes — and a 4xx would make the client render it as a fault.
    """
    pool = require_pool()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ai_service_url}/v1/playlists/compose",
                json={"brief": payload.brief, "limit": payload.limit},
            )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=503,
            detail="Playlist composition is unavailable. Try again shortly.",
        ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=502, detail="Playlist composition failed upstream."
        )

    proposal = response.json()
    if proposal.get("refused"):
        return {"refused": True, "reason": proposal.get("reason")}

    items = proposal["items"]

    # One transaction: a playlist that exists with no items, or with a rationale
    # describing talks it does not contain, is worse than no playlist. The
    # position unique constraint is deferrable, so the inserts can run in order
    # without an intermediate conflict.
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                playlist_id = await connection.fetchval(
                    """
                    INSERT INTO playlists (owner_id, title, generated_by, rationale)
                    VALUES ($1, $2, 'ai', $3)
                    RETURNING id
                    """,
                    user_id,
                    proposal["title"],
                    proposal["rationale"],
                )

                await connection.executemany(
                    """
                    INSERT INTO playlist_items
                        (playlist_id, video_id, position, start_sec, note)
                    VALUES ($1, $2::uuid, $3, $4, $5)
                    """,
                    [
                        (
                            playlist_id,
                            item["video_id"],
                            index,
                            int(item["start_sec"]),
                            item["excerpt"],
                        )
                        for index, item in enumerate(items)
                    ],
                )
    except Exception as error:
        # Retrieval and this write are separate queries against a catalogue that
        # a nightly ingest run edits. A talk removed between them is rare and
        # entirely possible, and it is worth a message someone can act on rather
        # than an opaque failure.
        if "foreign key" in str(error).lower():
            raise HTTPException(
                status_code=409,
                detail="The catalogue changed while this was being composed. Try again.",
            ) from error
        raise

    return {
        "refused": False,
        "id": str(playlist_id),
        "title": proposal["title"],
        "rationale": proposal["rationale"],
        "item_count": len(items),
    }
