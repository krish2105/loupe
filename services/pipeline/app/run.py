from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime

import asyncpg

from . import worker
from .asr import FixtureTranscriber, WhisperXTranscriber
from .budget import BudgetExhausted, ensure_budget, reserve
from .config import settings
from .embed import build_embedder
from .stages import STEPS_BY_NAME, eligible, requeue_failed, run_step

"""
The pipeline worker.

    uv run python -m app.run

Queue-driven and never blocking a request (§5). Each pass requeues anything
that failed and still has retries, then advances every eligible video one step.
Running it repeatedly is how a video gets from `transcoded` to `enriched`, and
running it twice over a finished catalogue costs four SELECTs.
"""

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("pipeline")


def build_transcriber():
    if settings.use_real_models:
        try:
            return WhisperXTranscriber()
        except RuntimeError as error:
            logger.warning("%s", error)

    logger.info(
        "using the fixture transcriber — output is generated, stored with "
        "engine='fixture', and is not a real transcript"
    )
    return FixtureTranscriber()


async def run_once(pool) -> dict:
    today = datetime.now(UTC).date()
    await ensure_budget(pool, settings.transcription_minutes_cap, today)

    transcriber = build_transcriber()
    embedder = build_embedder(prefer_real=settings.use_real_models)

    report: dict[str, int] = {"requeued": await requeue_failed(pool, settings.max_retries)}

    for name in ("transcribe", "chunk", "embed", "enrich"):
        step = STEPS_BY_NAME[name]
        rows = await eligible(pool, step, settings.batch_size)
        outcomes: dict[str, int] = {}

        for row in rows:
            video_id = row["id"]

            if name == "transcribe":
                # §10.3: the cap is checked before the work, by code.
                duration = await pool.fetchval(
                    "SELECT COALESCE(duration_sec, 0) FROM videos WHERE id = $1",
                    video_id,
                )
                try:
                    await reserve(pool, max(1, int(duration) // 60), today)
                except BudgetExhausted as stop:
                    logger.warning("%s", stop)
                    outcomes["budget_exhausted"] = outcomes.get("budget_exhausted", 0) + 1
                    break

            async def work(video_id=video_id, name=name):
                if name == "transcribe":
                    await worker.transcribe(pool, video_id, transcriber)
                elif name == "chunk":
                    await worker.chunk(pool, video_id)
                elif name == "embed":
                    await worker.embed(pool, video_id, embedder)
                else:
                    await worker.enrich(pool, video_id)

            outcome = await run_step(pool, video_id, step, work)
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

        if outcomes:
            report[name] = sum(outcomes.values())
            report[f"{name}_outcomes"] = outcomes  # type: ignore[assignment]

    return report


async def main() -> int:
    dsn = settings.database_url.replace("postgres://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        # Several passes, because one pass advances a video exactly one stage.
        combined = []
        for _ in range(5):
            report = await run_once(pool)
            combined.append(report)
            if not any(key in report for key in ("transcribe", "chunk", "embed", "enrich")):
                break

        stages = await pool.fetch(
            """
            SELECT processing_status::text AS stage, count(*) AS count
            FROM videos WHERE source_class = 'owned'
            GROUP BY 1 ORDER BY 1
            """
        )
    finally:
        await pool.close()

    print(
        json.dumps(
            {
                "passes": combined,
                "owned_by_stage": {row["stage"]: row["count"] for row in stages},
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
