from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

"""
The stage machine — §10.1 and §5.1.

    uploaded → transcoding → transcoded → transcribing → transcribed
             → chunking → embedding → indexed → enriched

    "Explicit, resumable states. Failures park at failed_<stage> with a retry
     count."

Two properties matter more than the transitions themselves:

**Resumable.** A crashed worker leaves a video in a running state with an
unfinished job row. The next run finds it and continues, rather than needing
someone to work out where it stopped.

**Idempotent** (§5.1). Every job is keyed on (video_id, stage, version). The
pipeline gets re-run many times during development, and the plan is explicit
that this should be free. A finished job is skipped; a re-run costs one SELECT.

Enrichment is deliberately the one step that cannot park as failed. §11 says a
chapter-detection failure renders an unsegmented scrubber — the talk stays
fully watchable and searchable, so parking it as broken would overstate what
went wrong.
"""

logger = logging.getLogger("pipeline")

MAX_RETRIES = 3


@dataclass(frozen=True)
class Step:
    name: str
    #: The status that makes a video eligible for this step.
    start: str
    #: The status held while the step runs.
    running: str
    #: The status on success.
    done: str
    #: The status on failure. None means the failure is non-fatal and the video
    #: returns to `start` — used where a missing output degrades rather than breaks.
    failed: str | None


STEPS: list[Step] = [
    # The transition this machine has documented since it was written, with
    # nothing behind it until now: transcoding was Bunny's job and Bunny was
    # never provisioned, so every video in the catalogue arrived already
    # `transcoded` from a fixture.
    Step("transcode", "uploaded", "transcoding", "transcoded", "failed_transcoding"),
    Step("transcribe", "transcoded", "transcribing", "transcribed", "failed_transcribing"),
    Step("chunk", "transcribed", "chunking", "embedding", "failed_chunking"),
    # Chunked-but-not-embedded parks at `embedding`, so the embed step is
    # separately resumable — re-embedding after a model change must not require
    # re-transcribing.
    Step("embed", "embedding", "embedding", "indexed", "failed_embedding"),
    Step("enrich", "indexed", "indexed", "enriched", None),
]

STEPS_BY_NAME = {step.name: step for step in STEPS}


class StepFailed(RuntimeError):
    """Raised by step work to park the video. Anything else parks it too."""


async def claim(pool, video_id, step: Step, version: int = 1) -> bool:
    """
    Take the job, or report that there is nothing to do.

    Returns False when a finished job already exists for this
    (video_id, stage, version) — which is what makes a re-run free.
    """
    existing = await pool.fetchrow(
        """
        SELECT id, finished_at FROM pipeline_jobs
        WHERE video_id = $1 AND stage = $2::processing_status AND version = $3
        """,
        video_id,
        step.running,
        version,
    )

    if existing and existing["finished_at"] is not None:
        return False

    await pool.execute(
        """
        INSERT INTO pipeline_jobs (video_id, stage, version, attempts, started_at)
        VALUES ($1, $2::processing_status, $3, 1, now())
        ON CONFLICT (video_id, stage, version) DO UPDATE
        SET attempts = pipeline_jobs.attempts + 1,
            started_at = now(),
            error = NULL
        """,
        video_id,
        step.running,
        version,
    )

    await pool.execute(
        "UPDATE videos SET processing_status = $2::processing_status WHERE id = $1",
        video_id,
        step.running,
    )
    return True


async def complete(pool, video_id, step: Step, version: int = 1) -> None:
    await pool.execute(
        """
        UPDATE pipeline_jobs SET finished_at = now(), error = NULL
        WHERE video_id = $1 AND stage = $2::processing_status AND version = $3
        """,
        video_id,
        step.running,
        version,
    )
    await pool.execute(
        """
        UPDATE videos
        SET processing_status = $2::processing_status, retry_count = 0
        WHERE id = $1
        """,
        video_id,
        step.done,
    )


async def park(pool, video_id, step: Step, error: str, version: int = 1) -> str:
    """
    Park the video where it failed, with a retry count.

    The status it lands in is the record of what broke. Nothing else needs to
    be consulted to know where to resume.
    """
    await pool.execute(
        """
        UPDATE pipeline_jobs SET error = $4
        WHERE video_id = $1 AND stage = $2::processing_status AND version = $3
        """,
        video_id,
        step.running,
        version,
        error[:2000],
    )

    landing = step.failed or step.start
    await pool.execute(
        """
        UPDATE videos
        SET processing_status = $2::processing_status, retry_count = retry_count + 1
        WHERE id = $1
        """,
        video_id,
        landing,
    )
    return landing


async def run_step(
    pool,
    video_id,
    step: Step,
    work: Callable[[], Awaitable[None]],
    version: int = 1,
) -> str:
    """
    Run one step against one video, and leave the row in a state that says what
    happened. Never raises — a worker that dies on the first bad video stops
    processing every good one behind it.
    """
    if not await claim(pool, video_id, step, version):
        return "skipped"

    try:
        await work()
    except Exception as error:  # noqa: BLE001 — everything parks, nothing escapes
        landing = await park(pool, video_id, step, repr(error), version)
        logger.warning("%s failed for %s: %r", step.name, video_id, error)
        return landing

    await complete(pool, video_id, step, version)
    return step.done


async def requeue_failed(pool, max_retries: int = MAX_RETRIES) -> int:
    """
    Move parked videos back to their step's starting state, while they still
    have retries left.

    Separate from the runner on purpose: a step that failed for a transient
    reason should be retried on the next pass, not immediately in a tight loop
    that reproduces the same failure three times in a second.
    """
    moved = 0
    for step in STEPS:
        if step.failed is None:
            continue

        result = await pool.execute(
            """
            UPDATE videos
            SET processing_status = $1::processing_status
            WHERE processing_status = $2::processing_status
              AND retry_count < $3
            """,
            step.start,
            step.failed,
            max_retries,
        )
        moved += int(result.split()[-1]) if result.startswith("UPDATE") else 0

    return moved


async def eligible(pool, step: Step, limit: int = 20) -> list:
    """Owned videos waiting on this step. Class B never enters the pipeline (§4)."""
    return await pool.fetch(
        """
        SELECT id FROM videos
        WHERE source_class = 'owned'
          AND processing_status = $1::processing_status
        ORDER BY created_at
        LIMIT $2
        """,
        step.start,
        limit,
    )
