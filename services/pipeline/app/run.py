from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime

import asyncpg

from . import worker
from .asr import FixtureTranscriber, GroqTranscriber, WhisperXTranscriber
from .budget import BudgetExhausted, ensure_budget, reserve
from .config import settings
from .embed import build_embedder
from .stages import STEPS_BY_NAME, eligible, requeue_failed, run_step


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
    # A password that is obviously still a placeholder. Postgres answers this
    # with `password authentication failed for user "postgres"`, which is true
    # and sends people to reset a password that was never wrong.
    password = ""
    if "@" in url:
        credentials = url.split("://", 1)[1].rsplit("@", 1)[0]
        password = credentials.split(":", 1)[1] if ":" in credentials else ""

    stripped = password.strip("[]<>{}").replace("-", "").replace("_", "").lower()
    if stripped in {"yourpassword", "password", "changeme", "yourdbpassword"} or (
        password.startswith("<") and password.endswith(">")
    ):
        raise RuntimeError(
            f"DATABASE_URL still has a placeholder password ({password!r}).\n"
            "Replace it with the real one from Supabase → Project Settings → "
            "Database.\n"
            "Set it once instead of pasting it repeatedly:\n"
            '  export LOUPE_DB="postgresql://...", then use "$LOUPE_DB"'
        )

    # asyncpg accepts both schemes; normalising means one form downstream.
    return url.replace("postgres://", "postgresql://", 1)


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
    """
    The best real transcriber available, or the fixture with a warning.

    Groq first. It satisfies §5.2's hard requirement — word-level timestamps —
    without WhisperX's gigabyte of torch wheels, and the free tier transcribes
    more than this catalogue will hold. WhisperX stays as the local option for
    anything that must not leave the machine.
    """
    if settings.groq_api_key:
        try:
            return GroqTranscriber(settings.groq_api_key)
        except RuntimeError as error:
            logger.warning("%s", error)

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

    for name in ("transcode", "transcribe", "chunk", "embed", "enrich"):
        step = STEPS_BY_NAME[name]
        rows = await eligible(pool, step, settings.batch_size)
        outcomes: dict[str, int] = {}

        if name == "transcribe" and transcriber.needs_audio_file:
            # A real recogniser needs audio, and the only assets we can supply
            # audio for are the ones whose source is in our own bucket. A
            # referenced stream has no source file to extract from, so handing
            # one to the transcriber fails and the stage machine records the
            # video as broken — which it is not. It is not ours to transcribe.
            #
            # Declining is not silent: the count is reported, because a
            # catalogue where most talks are quietly skipped is something the
            # operator should see rather than infer.
            playable = await pool.fetch(
                """
                SELECT v.id FROM videos v
                JOIN video_assets a ON a.video_id = v.id
                WHERE v.id = ANY($1::uuid[]) AND a.provider = 's3'
                """,
                [row["id"] for row in rows],
            )
            ours = {row["id"] for row in playable}
            declined = len(rows) - len(ours)
            if declined:
                report["transcribe_declined_no_audio"] = declined
                logger.info(
                    "%d video(s) skipped: %s needs an audio file and their media "
                    "is not hosted here",
                    declined,
                    transcriber.engine,
                )
            rows = [row for row in rows if row["id"] in ours]

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
                if name == "transcode":
                    await worker.transcode_video(pool, video_id)
                elif name == "transcribe":
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
    dsn = _checked_dsn(settings.database_url)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, statement_cache_size=0)
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
