from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..config import settings
from ..playback import playable_url

"""
Catalogue reads: the feed, a video, a channel.

Every response carries explicit capability flags rather than making the client
infer them from processing_status. §4 makes the Class A / Class B asymmetry a
first-class domain concept, and §4.2 rule 4 says the unavailable states have to
be designed early — which is only possible if the API says plainly what a given
video can and cannot do.
"""

router = APIRouter(prefix="/v1", tags=["catalogue"])

# A video is searchable and answerable only once the pipeline has indexed it.
SEARCHABLE_STAGES = ("indexed", "enriched")

VIDEO_COLUMNS = """
    v.id, v.title, v.description, v.duration_sec, v.published_at,
    v.source_class::text AS source_class,
    v.content_kind::text AS content_kind,
    v.processing_status::text AS processing_status,
    c.id AS channel_id, c.handle AS channel_handle, c.name AS channel_name,
    c.avatar_url AS channel_avatar,
    COALESCE(s.view_count, 0) AS view_count,
    COALESCE(s.comment_count, 0) AS comment_count
"""

VIDEO_JOINS = """
    FROM videos v
    JOIN channels c ON c.id = v.channel_id
    LEFT JOIN video_stats s ON s.video_id = v.id
"""


def serialise(row) -> dict:
    status = row["processing_status"]
    is_owned = row["source_class"] == "owned"

    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "duration_sec": row["duration_sec"],
        "published_at": row["published_at"].isoformat() if row["published_at"] else None,
        "source_class": row["source_class"],
        # ADR 0003. One column rather than a parallel schema, so every surface
        # that already renders a video renders an episode by branching on this
        # instead of by reading a different table.
        "content_kind": row["content_kind"],
        "processing_status": status,
        "channel": {
            "id": str(row["channel_id"]),
            "handle": row["channel_handle"],
            "name": row["channel_name"],
            "avatar_url": row["channel_avatar"],
        },
        "view_count": row["view_count"],
        "comment_count": row["comment_count"],
        # The capability matrix from §4, stated rather than implied.
        "capabilities": {
            "playable": is_owned and status not in ("uploaded", "transcoding"),
            "searchable_inside": is_owned and status in SEARCHABLE_STAGES,
            "askable": is_owned and status in SEARCHABLE_STAGES,
            "has_chapters": is_owned and status in SEARCHABLE_STAGES,
            "processing": is_owned and status not in SEARCHABLE_STAGES,
        },
    }


def encode_cursor(published_at: datetime, video_id: UUID) -> str:
    raw = f"{published_at.isoformat()}|{video_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        timestamp, video_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return datetime.fromisoformat(timestamp), UUID(video_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor.") from None


def require_pool():
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return pool


@router.get("/feed")
async def feed(
    limit: int = Query(24, ge=1, le=60),
    cursor: str | None = None,
    only: str | None = Query(None, pattern="^searchable$"),
) -> dict[str, object]:
    """
    The home feed, newest first.

    Keyset pagination on (published_at, id) rather than OFFSET: the feed gains
    rows while someone is scrolling it, and OFFSET silently repeats or skips
    items when that happens.

    `only=searchable` narrows to talks you can search inside — a real filter
    over the §4 capability split rather than a decorative one, and the clearest
    way to show that the two content classes genuinely differ.
    """
    pool = require_pool()

    searchable_clause = (
        " AND v.source_class = 'owned' AND v.processing_status IN ('indexed', 'enriched')"
        if only == "searchable"
        else ""
    )

    if cursor:
        before_time, before_id = decode_cursor(cursor)
        rows = await pool.fetch(
            f"""
            SELECT {VIDEO_COLUMNS}
            {VIDEO_JOINS}
            WHERE v.visibility = 'public'
              AND (v.published_at, v.id) < ($1, $2)
              {searchable_clause}
            ORDER BY v.published_at DESC, v.id DESC
            LIMIT $3
            """,
            before_time,
            before_id,
            limit,
        )
    else:
        rows = await pool.fetch(
            f"""
            SELECT {VIDEO_COLUMNS}
            {VIDEO_JOINS}
            WHERE v.visibility = 'public'
              {searchable_clause}
            ORDER BY v.published_at DESC, v.id DESC
            LIMIT $1
            """,
            limit,
        )

    items = [serialise(row) for row in rows]
    next_cursor = (
        encode_cursor(rows[-1]["published_at"], rows[-1]["id"])
        if len(rows) == limit and rows[-1]["published_at"]
        else None
    )

    return {"items": items, "next_cursor": next_cursor}


@router.get("/shorts")
async def shorts(limit: int = Query(12, ge=1, le=30)) -> dict[str, object]:
    """
    The vertical feed (§3.1, §13).

    Returns the playback URL with each item rather than making the client fetch
    it per video. §13 requires preloading the next two manifests, and a feed
    that had to make a round-trip before it could preload would defeat the
    point of preloading.

    The limit is low on purpose. A vertical feed is scrolled, not paged, and
    handing the client thirty items means thirty rows of metadata for two that
    will be watched.
    """
    pool = require_pool()

    rows = await pool.fetch(
        f"""
        SELECT {VIDEO_COLUMNS}, a.hls_url
        {VIDEO_JOINS}
        LEFT JOIN video_assets a ON a.video_id = v.id
        WHERE v.is_short AND v.visibility = 'public'
        ORDER BY v.published_at DESC NULLS LAST, v.id DESC
        LIMIT $1
        """,
        limit,
    )

    items = []
    for row in rows:
        payload = serialise(row)
        payload["hls_url"] = playable_url(row["hls_url"], settings.media_service_url)
        items.append(payload)

    return {"items": items}


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(36, ge=1, le=60),
) -> dict[str, object]:
    """
    Keyword search over titles, descriptions, and channel names.

    This is the §4 baseline that works for *both* content classes — Class B
    carries no transcript, so title and description is all there is. Semantic
    search inside transcripts is Phase 6 and is a different query against
    transcript_chunks; this endpoint stays as the fallback §11 requires when
    embeddings are unavailable, and as the only option for referenced content.

    Ranked with ts_rank over a weighted document so a title match outranks a
    description mention, rather than ordering by date and hoping.
    """
    pool = require_pool()

    rows = await pool.fetch(
        f"""
        SELECT {VIDEO_COLUMNS},
               ts_rank(
                 setweight(to_tsvector('english', v.title), 'A') ||
                 setweight(to_tsvector('english', coalesce(v.description, '')), 'C') ||
                 setweight(to_tsvector('english', c.name), 'B'),
                 websearch_to_tsquery('english', $1)
               ) AS rank
        {VIDEO_JOINS}
        WHERE v.visibility = 'public'
          AND (
            setweight(to_tsvector('english', v.title), 'A') ||
            setweight(to_tsvector('english', coalesce(v.description, '')), 'C') ||
            setweight(to_tsvector('english', c.name), 'B')
          ) @@ websearch_to_tsquery('english', $1)
        ORDER BY rank DESC, v.published_at DESC
        LIMIT $2
        """,
        q,
        limit,
    )

    return {
        "query": q,
        "items": [serialise(row) for row in rows],
        # §11: semantic search degrades to keyword-only, flagged in the UI. It
        # is flagged from the very first version rather than being added when
        # the semantic path exists.
        "mode": "keyword",
    }


@router.get("/videos/{video_id}")
async def video_detail(video_id: UUID) -> dict[str, object]:
    pool = require_pool()

    row = await pool.fetchrow(
        f"""
        SELECT {VIDEO_COLUMNS}, a.hls_url
        {VIDEO_JOINS}
        LEFT JOIN video_assets a ON a.video_id = v.id
        WHERE v.id = $1 AND v.visibility = 'public'
        """,
        video_id,
    )

    if row is None:
        raise HTTPException(status_code=404, detail="No such talk.")

    payload = serialise(row)
    # The column holds an absolute URL for the seeded reference stream and a
    # bucket key for anything our transcoder produced; only the second needs
    # the media service to become openable (§5.1).
    payload["hls_url"] = (
        playable_url(row["hls_url"], settings.media_service_url)
        if payload["capabilities"]["playable"]
        else None
    )
    return payload


@router.get("/videos/{video_id}/related")
async def related(video_id: UUID, limit: int = Query(8, ge=1, le=24)) -> dict[str, object]:
    """
    The related rail.

    Same channel first, then anything recent. Content-similarity neighbours
    replace this in Phase 9 (§12.1) — until then this is honest ordering rather
    than a recommendation dressed up as one.
    """
    pool = require_pool()

    rows = await pool.fetch(
        f"""
        SELECT {VIDEO_COLUMNS}
        {VIDEO_JOINS}
        WHERE v.visibility = 'public'
          AND v.id <> $1
        ORDER BY (v.channel_id = (SELECT channel_id FROM videos WHERE id = $1)) DESC,
                 v.published_at DESC
        LIMIT $2
        """,
        video_id,
        limit,
    )

    return {"items": [serialise(row) for row in rows]}


@router.get("/channels/{handle}")
async def channel(handle: str, limit: int = Query(24, ge=1, le=60)) -> dict[str, object]:
    pool = require_pool()

    channel_row = await pool.fetchrow(
        """
        SELECT id, handle, name, description, avatar_url, banner_url,
               source_class::text AS source_class
        FROM channels WHERE handle = $1
        """,
        handle,
    )

    if channel_row is None:
        raise HTTPException(status_code=404, detail="No such channel.")

    rows = await pool.fetch(
        f"""
        SELECT {VIDEO_COLUMNS}
        {VIDEO_JOINS}
        WHERE v.channel_id = $1 AND v.visibility = 'public'
        ORDER BY v.published_at DESC, v.id DESC
        LIMIT $2
        """,
        channel_row["id"],
        limit,
    )

    return {
        "channel": {
            "id": str(channel_row["id"]),
            "handle": channel_row["handle"],
            "name": channel_row["name"],
            "description": channel_row["description"],
            "avatar_url": channel_row["avatar_url"],
            "banner_url": channel_row["banner_url"],
            "source_class": channel_row["source_class"],
        },
        "videos": [serialise(row) for row in rows],
    }


# ------------------------------------------------------------- audio mode ---
# ADR 0003. These endpoints exist because audio needs the playback URL and the
# transcript up front, not because audio is a different kind of content. The
# feed, search, channel, and collection endpoints already serve episodes
# unchanged, which is the point of one content_kind column instead of a second
# schema.


@router.get("/listen")
async def listen_feed(limit: int = Query(24, ge=1, le=60)) -> dict[str, object]:
    """
    Episodes, newest first.

    The playback URL rides along for the same reason it does on /shorts: the
    queue needs a source the moment someone presses play on a card, and a
    round-trip per track would make "play all" stutter between every episode.
    """
    pool = require_pool()

    rows = await pool.fetch(
        f"""
        SELECT {VIDEO_COLUMNS}, a.hls_url
        {VIDEO_JOINS}
        LEFT JOIN video_assets a ON a.video_id = v.id
        WHERE v.content_kind = 'audio' AND v.visibility = 'public'
        ORDER BY v.published_at DESC NULLS LAST, v.id DESC
        LIMIT $1
        """,
        limit,
    )

    items = []
    for row in rows:
        payload = serialise(row)
        payload["hls_url"] = playable_url(row["hls_url"], settings.media_service_url)
        items.append(payload)

    return {"items": items}


@router.get("/videos/{video_id}/transcript")
async def transcript(video_id: UUID) -> dict[str, object]:
    """
    The transcript, as lines short enough to read while listening.

    Built from word timings, not from `transcript_chunks`. The first version did
    use the chunks, because they were already there and already carried
    timestamps, and it was wrong in a way that only showed up on screen: chunks
    are 300 to 600 tokens (§10.2), sized so a retrieval hit has enough context
    to answer from. On a forty-minute episode that is a three-and-a-half minute
    wall of text per line. A transcript view whose smallest unit is three
    minutes is not synced to anything.

    So lines are built by grouping words up to a sentence end or a length cap,
    and each line's start is the start of its first word. §11.1 calls word-level
    ASR non-negotiable because citation accuracy depends on it; this is the
    second thing that depends on it.

    ADR 0003 makes the case that this panel is the argument for spoken audio
    over CC music. In a music app it is lyrics and needs licensed data. Here it
    is content Loupe already produced, timed to the word.
    """
    pool = require_pool()

    row = await pool.fetchrow(
        """
        SELECT t.segments
        FROM transcripts t
        JOIN videos v ON v.id = t.video_id
        WHERE t.video_id = $1 AND v.visibility = 'public'
        """,
        video_id,
    )

    if row is None:
        return {"available": False, "lines": []}

    segments = row["segments"]
    if isinstance(segments, str):
        segments = json.loads(segments)

    return {"available": len(segments) > 0, "lines": build_lines(segments)}


#: Roughly one screen line at reading width. A cap rather than a target: lines
#: end at sentence boundaries wherever there is one, and this only breaks up
#: speech that runs on without punctuation, which ASR output frequently does.
LINE_CHAR_CAP = 140

_SENTENCE_END = (".", "!", "?")


def build_lines(segments: list[dict]) -> list[dict]:
    """
    Group timed words into readable lines.

    Pure and separate from the query so the grouping can be tested without a
    database, which matters because the off-by-one at a sentence boundary is
    invisible until someone reads along and the highlight is one line ahead.
    """
    lines: list[dict] = []
    words: list[str] = []
    start: float | None = None
    end = 0.0
    speaker: str | None = None

    def flush() -> None:
        nonlocal words, start, end, speaker
        if not words or start is None:
            return
        lines.append(
            {
                "index": len(lines),
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "speaker": speaker,
                "text": " ".join(words),
            }
        )
        words = []
        start = None

    for segment in segments:
        word = str(segment.get("w", "")).strip()
        if not word:
            continue

        # A speaker change always breaks the line. Merging two speakers into one
        # line makes an interview unreadable.
        turn = segment.get("spk")
        if words and turn != speaker:
            flush()

        if start is None:
            start = float(segment.get("s", end))
            speaker = turn

        words.append(word)
        end = float(segment.get("e", start))

        length = sum(len(part) + 1 for part in words)
        if word.endswith(_SENTENCE_END) or length >= LINE_CHAR_CAP:
            flush()

    flush()
    return lines


@router.get("/videos/{video_id}/radio")
async def radio(video_id: UUID, limit: int = Query(20, ge=1, le=50)) -> dict[str, object]:
    """
    A queue built outward from one episode (ADR 0003).

    Reads `video_similarity`, which §6.4 defined in Phase 0 and which nothing
    used until the Phase 9 recommender populated it. That table is content
    similarity, so a radio station is neighbours-of-neighbours rather than
    anything personalised, and it says so rather than implying a model.

    Falls back to the same show when there are no neighbours, which is the case
    for any episode indexed before the similarity job last ran. An empty radio
    queue would be a worse answer than an obvious one.
    """
    pool = require_pool()

    rows = await pool.fetch(
        f"""
        WITH neighbours AS (
            SELECT s.neighbour_id AS id, s.similarity
            FROM video_similarity s
            WHERE s.video_id = $1
            ORDER BY s.rank
            LIMIT $2
        )
        SELECT {VIDEO_COLUMNS}, a.hls_url, n.similarity
        {VIDEO_JOINS}
        JOIN neighbours n ON n.id = v.id
        LEFT JOIN video_assets a ON a.video_id = v.id
        WHERE v.visibility = 'public'
        ORDER BY n.similarity DESC
        """,
        video_id,
        limit,
    )

    source = "similarity"

    if not rows:
        source = "same_show"
        rows = await pool.fetch(
            f"""
            SELECT {VIDEO_COLUMNS}, a.hls_url
            {VIDEO_JOINS}
            LEFT JOIN video_assets a ON a.video_id = v.id
            WHERE v.visibility = 'public'
              AND v.id <> $1
              AND v.channel_id = (SELECT channel_id FROM videos WHERE id = $1)
            ORDER BY v.published_at DESC NULLS LAST
            LIMIT $2
            """,
            video_id,
            limit,
        )

    items = []
    for row in rows:
        payload = serialise(row)
        payload["hls_url"] = playable_url(row["hls_url"], settings.media_service_url)
        items.append(payload)

    return {"source": source, "items": items}
