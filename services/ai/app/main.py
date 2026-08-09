from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .answering import ExtractiveAnswerer, GeneratedAnswerer
from .config import settings
from .embed import build_embedder
from .playlists import MAX_ITEMS, MIN_ITEMS, VideoCard, compose
from .retrieval import (
    ModelMismatch,
    RetrievedChunk,
    search_across_catalogue,
    search_within_video,
)
from .summarise import summarise


def _checked_dsn(url: str) -> str:
    """
    Turn a bad DATABASE_URL into one sentence instead of a stack trace.

    asyncpg's own message for an unreplaced placeholder is `invalid DSN: scheme
    is expected to be either "postgresql" or "postgres", got ''`, under thirty
    lines of traceback through the connection pool. It is accurate and it does
    not say which variable, where it came from, or what it should look like.
    """
    if not url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            f"DATABASE_URL is not a connection string (got {url[:60]!r}).\n"
            "It must start with postgresql:// — for example\n"
            "  postgresql://postgres.<ref>:<password>@aws-0-<region>"
            ".pooler.supabase.com:6543/postgres\n"
            "If that looks like a placeholder, it was pasted without being "
            "replaced."
        )
    # asyncpg accepts both schemes; normalising means one form downstream.
    return url.replace("postgres://", "postgresql://", 1)


"""
The AI service — §5.

Owns summarising, ask-video, and semantic search, and is the only service that
holds a model key or contains a prompt.

Every endpoint here implements a contract from §11 with an explicit failure
mode, because that is the level at which the plan says a technical lead reviews
this: input, output, what happens when it fails, and what gets cached.
"""

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = _checked_dsn(settings.database_url)
    try:
        _state["pool"] = await asyncpg.create_pool(
            dsn, min_size=1, max_size=8, statement_cache_size=0
        )
    except (OSError, asyncpg.PostgresError):
        _state["pool"] = None

    # Loading the embedder is slow and happens once. Doing it per request would
    # make the first question of every session take thirty seconds.
    _state["embedder"] = build_embedder(prefer_real=settings.use_real_embeddings)
    _state["answerer"] = (
        GeneratedAnswerer(settings.gemini_api_key)
        if settings.gemini_api_key
        else ExtractiveAnswerer()
    )

    yield

    if _state.get("pool"):
        await _state["pool"].close()


app = FastAPI(title="Loupe AI service", version="0.1.0", lifespan=lifespan)

# Without this every browser call fails preflight. The web app is a different
# origin from every service by construction, so this is not an edge case — it
# is the only way the client ever talks to them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def pool():
    if _state.get("pool") is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return _state["pool"]


def serialise_citation(chunk: RetrievedChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "start_sec": chunk.start_sec,
        "end_sec": chunk.end_sec,
        "text": chunk.text_display,
        "score": round(chunk.similarity, 4),
    }


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "embedder": _state.get("embedder").model_id if _state.get("embedder") else None,
        "answerer": _state.get("answerer").model if _state.get("answerer") else None,
        "database": "ok" if _state.get("pool") else "unavailable",
    }


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    session_id: UUID | None = None


@app.post("/v1/videos/{video_id}/ask")
async def ask(video_id: UUID, payload: Question) -> dict[str, object]:
    """
    §11 ask-video. Refuses rather than guessing (§11.1).

    The refusal decision is made from the retrieval score before anything is
    generated. Every turn is persisted — §6.3 notes ask_turns doubles as the
    raw material for the §11.2 eval set, and refusal rate is a headline metric,
    so it is a stored column rather than something inferred from answer text.
    """
    connection = pool()
    embedder = _state["embedder"]
    answerer = _state["answerer"]

    [query_vector] = embedder.embed([payload.question])

    try:
        chunks = await search_within_video(
            connection, video_id, query_vector, embedder.model_id
        )
    except ModelMismatch as mismatch:
        raise HTTPException(status_code=409, detail=str(mismatch)) from mismatch

    answer = await answerer.answer(payload.question, chunks)

    session_id = payload.session_id
    if session_id is None:
        session_id = await connection.fetchval(
            "INSERT INTO ask_sessions (video_id) VALUES ($1) RETURNING id", video_id
        )

    turn_index = await connection.fetchval(
        "SELECT COALESCE(max(turn_index) + 1, 0) FROM ask_turns WHERE session_id = $1",
        session_id,
    )

    await connection.execute(
        """
        INSERT INTO ask_turns
            (session_id, turn_index, question, answer, cited_chunk_ids,
             refused, top_score, model)
        VALUES ($1, $2, $3, $4, $5::uuid[], $6, $7, $8)
        """,
        session_id,
        turn_index,
        payload.question,
        None if answer.refused else answer.text,
        [chunk.chunk_id for chunk in answer.citations],
        answer.refused,
        answer.top_score,
        answer.model,
    )

    return {
        "session_id": str(session_id),
        "answer": answer.text,
        "refused": answer.refused,
        "citations": [serialise_citation(chunk) for chunk in answer.citations],
        "top_score": round(answer.top_score, 4),
        "model": answer.model,
    }


@app.get("/v1/videos/{video_id}/summary")
async def summary(video_id: UUID) -> dict[str, object]:
    """
    §11 summariser. Cached permanently; hidden entirely rather than partial.
    """
    connection = pool()

    cached = await connection.fetchrow(
        "SELECT model, tldr, key_points FROM video_summaries WHERE video_id = $1",
        video_id,
    )
    if cached:
        points = cached["key_points"]
        return {
            "available": True,
            "tldr": cached["tldr"],
            "key_points": json.loads(points) if isinstance(points, str) else points,
            "model": cached["model"],
            "cached": True,
        }

    rows = await connection.fetch(
        """
        SELECT text_display, start_sec, embedding
        FROM transcript_chunks
        WHERE video_id = $1 AND embedding IS NOT NULL
        ORDER BY chunk_index
        """,
        video_id,
    )

    def parse(value) -> list[float]:
        if isinstance(value, str):
            return [float(part) for part in value.strip("[]").split(",")]
        return list(value)

    result = summarise(
        [row["text_display"] for row in rows],
        [float(row["start_sec"]) for row in rows],
        [parse(row["embedding"]) for row in rows],
    )

    if result is None:
        # Hide the block rather than showing something partial.
        return {"available": False, "reason": "not enough indexed content"}

    key_points = [
        {"text": point.text, "start_sec": point.start_sec} for point in result.key_points
    ]

    await connection.execute(
        """
        INSERT INTO video_summaries (video_id, model, tldr, key_points)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (video_id) DO UPDATE
        SET model = EXCLUDED.model, tldr = EXCLUDED.tldr,
            key_points = EXCLUDED.key_points, generated_at = now()
        """,
        video_id,
        result.model,
        result.tldr,
        json.dumps(key_points),
    )

    return {
        "available": True,
        "tldr": result.tldr,
        "key_points": key_points,
        "model": result.model,
        "cached": False,
    }


@app.get("/v1/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, object]:
    """
    §11 semantic search: ranked videos, each with its best-matching moment.

    On failure it degrades to keyword-only *and says so* — the `mode` field is
    what the UI flags, so a degraded search is never silently presented as the
    real thing.
    """
    connection = pool()
    embedder = _state["embedder"]

    [query_vector] = embedder.embed([q])
    chunks = await search_across_catalogue(
        connection, query_vector, embedder.model_id, limit
    )

    if not chunks:
        return {"query": q, "mode": "semantic", "items": []}

    videos = await connection.fetch(
        """
        SELECT v.id, v.title, v.duration_sec, c.name AS channel_name, c.handle
        FROM videos v JOIN channels c ON c.id = v.channel_id
        WHERE v.id = ANY($1::uuid[])
        """,
        [chunk.video_id for chunk in chunks],
    )
    by_id = {str(row["id"]): row for row in videos}

    items = []
    for chunk in chunks:
        video = by_id.get(chunk.video_id)
        if video is None:
            continue
        items.append(
            {
                "video_id": chunk.video_id,
                "title": video["title"],
                "channel_name": video["channel_name"],
                "channel_handle": video["handle"],
                "duration_sec": video["duration_sec"],
                # The moment, which is the entire point — a semantic result
                # that only named the video would concede the thesis.
                "moment": serialise_citation(chunk),
            }
        )

    return {"query": q, "mode": "semantic", "items": items}


class PlaylistBrief(BaseModel):
    brief: str = Field(min_length=8, max_length=300)
    limit: int = Field(default=8, ge=MIN_ITEMS, le=MAX_ITEMS)


@app.post("/v1/playlists/compose")
async def compose_playlist(payload: PlaylistBrief) -> dict[str, object]:
    """
    §11 AI playlists: a brief in, an ordered list plus a written rationale out.

    This proposes; it does not persist. Writing the playlist means knowing who
    owns it, and §5 puts ownership and authorisation in the core API — which
    calls this. Keeping the write on the other side of that line is what stops
    the AI service from needing to verify a session token.

    Retrieval only. No model is called, so this spends nothing against the §10.3
    ceiling.
    """
    connection = pool()
    embedder = _state["embedder"]

    [query_vector] = embedder.embed([payload.brief])

    # Deliberately over-fetched: the floor and the channel spread both discard
    # candidates, so retrieving exactly `limit` would guarantee a short list.
    chunks = await search_across_catalogue(
        connection, query_vector, embedder.model_id, limit=payload.limit * 5
    )

    rows = await connection.fetch(
        """
        SELECT v.id, v.title, c.id AS channel_id, c.name AS channel_name
        FROM videos v JOIN channels c ON c.id = v.channel_id
        WHERE v.id = ANY($1::uuid[])
        """,
        [chunk.video_id for chunk in chunks],
    )
    cards = {
        str(row["id"]): VideoCard(
            video_id=str(row["id"]),
            title=row["title"],
            channel_id=str(row["channel_id"]),
            channel_name=row["channel_name"],
        )
        for row in rows
    }

    proposal = compose(payload.brief, chunks, cards, limit=payload.limit)

    if proposal.refused:
        return {"refused": True, "reason": proposal.reason, "title": proposal.title}

    return {
        "refused": False,
        "title": proposal.title,
        "rationale": proposal.rationale,
        "items": [
            {
                "video_id": item.video_id,
                "title": item.title,
                "channel_name": item.channel_name,
                "start_sec": item.start_sec,
                "excerpt": item.excerpt,
                "score": item.score,
            }
            for item in proposal.items
        ],
    }
