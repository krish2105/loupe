from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .config import settings

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
