from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db
from .auth import require_user_id
from .config import settings
from .routers import catalogue, collections, comments, studio

"""
Loupe core API.

§5 boundary rules, which hold from Phase 0 rather than being retrofitted:

  - This service owns CRUD, authorisation, feed assembly, and search
    orchestration. It is stateless and horizontally scalable.
  - It never holds media provider credentials. Those belong to the media
    service alone.
  - It never calls an LLM. That belongs to the AI service, which owns all
    prompts and model routing.

Both of those are easy to violate the first time something is urgent, so they
are written here where the violation would be made.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(
    title="Loupe core API",
    version="0.1.0",
    lifespan=lifespan,
)

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

app.include_router(catalogue.router)
app.include_router(collections.router)
app.include_router(comments.router)
app.include_router(studio.router)


@app.get("/health")
async def health() -> dict[str, object]:
    """Liveness plus a real database round-trip, not just a process check."""
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
    }


@app.get("/v1/pipeline/stages")
async def pipeline_stages() -> dict[str, object]:
    """
    Video counts per processing stage — the §14 pipeline dashboard.

    Reads the single processing_status enum that §5.1 requires, which is why
    this is one grouped query rather than a count per boolean flag.
    """
    pool = db.pool()
    if pool is None:
        return {"stages": {}, "database": "unavailable"}

    rows = await pool.fetch(
        """
        SELECT processing_status::text AS stage, count(*) AS count
        FROM videos
        GROUP BY processing_status
        ORDER BY processing_status
        """
    )

    return {
        "stages": {row["stage"]: row["count"] for row in rows},
        "database": "ok",
    }


class WatchEvent(BaseModel):
    video_id: UUID
    position_sec: int = Field(ge=0)
    watch_pct: float = Field(ge=0, le=1)
    completed: bool = False


@app.post("/v1/watch-events", status_code=204)
async def record_watch_event(
    event: WatchEvent,
    user_id: UUID = Depends(require_user_id),
) -> Response:
    """
    Append one watch event (§9.1).

    Append-only by §6.5: this never updates a row. Resume position is derived
    on read instead, which is what keeps the table usable as recommendation
    training data later rather than requiring a schema migration to get the
    history back.

    Returns 204 because the client fires these and does not wait — a body would
    be read by nobody.
    """
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO watch_events
                    (user_id, video_id, position_sec, watch_pct, completed)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                event.video_id,
                event.position_sec,
                event.watch_pct,
                event.completed,
            )
    except Exception as error:
        # A foreign key violation here means an unknown video or user, which is
        # a client error rather than a server fault.
        if "foreign key" in str(error).lower():
            raise HTTPException(status_code=404, detail="Unknown video.") from error
        raise

    return Response(status_code=204)


# §9.1: resume when a prior event exists past ten seconds and under 95%.
RESUME_MIN_SEC = 10
RESUME_MAX_PCT = 0.95


@app.get("/v1/videos/{video_id}/resume")
async def resume_position(
    video_id: UUID,
    user_id: UUID = Depends(require_user_id),
) -> dict[str, object]:
    """
    Where to pick this talk up, if anywhere.

    A read-side aggregate over the append-only log (§6.5). The most recent
    event wins; the thresholds keep the offer off talks barely started or
    effectively finished, because a resume prompt at four seconds in is noise.
    """
    pool = db.pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            """
            SELECT position_sec, watch_pct, completed
            FROM watch_events
            WHERE user_id = $1 AND video_id = $2
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
            """,
            user_id,
            video_id,
        )

    if (
        row is None
        or row["completed"]
        or row["position_sec"] <= RESUME_MIN_SEC
        or row["watch_pct"] >= RESUME_MAX_PCT
    ):
        return {"position_sec": None}

    return {"position_sec": row["position_sec"]}
