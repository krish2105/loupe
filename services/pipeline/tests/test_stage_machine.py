from app.stages import STEPS_BY_NAME, eligible, requeue_failed, run_step

from .conftest import retries_of, status_of

"""
The Phase 5 gate: "stage machine survives forced failure injection."

So failures are injected, deliberately, at each stage — not simulated by
mocking the machine, but by giving it work that raises. What is asserted is
that the video always lands somewhere that says what happened and where to
resume, and that nothing is ever lost or silently retried forever.
"""

TRANSCRIBE = STEPS_BY_NAME["transcribe"]
CHUNK = STEPS_BY_NAME["chunk"]
EMBED = STEPS_BY_NAME["embed"]
ENRICH = STEPS_BY_NAME["enrich"]


async def succeeds():
    return None


async def explodes():
    raise RuntimeError("injected failure")


class TestHappyPath:
    async def test_a_successful_step_advances_the_video(self, pool, owned_video):
        outcome = await run_step(pool, owned_video, TRANSCRIBE, succeeds)

        assert outcome == "transcribed"
        assert await status_of(pool, owned_video) == "transcribed"

    async def test_success_clears_the_retry_count(self, pool, owned_video):
        await run_step(pool, owned_video, TRANSCRIBE, explodes)
        await requeue_failed(pool)
        await run_step(pool, owned_video, TRANSCRIBE, succeeds)

        # A video that eventually succeeds must not carry a scar that pushes it
        # over the retry limit the next time anything goes wrong.
        assert await retries_of(pool, owned_video) == 0


class TestForcedFailureInjection:
    async def test_a_failure_parks_at_the_matching_stage(self, pool, owned_video):
        outcome = await run_step(pool, owned_video, TRANSCRIBE, explodes)

        # §10.1: "Failures park at failed_<stage> with a retry count."
        assert outcome == "failed_transcribing"
        assert await status_of(pool, owned_video) == "failed_transcribing"
        assert await retries_of(pool, owned_video) == 1

    async def test_the_failure_is_recorded_on_the_job(self, pool, owned_video):
        await run_step(pool, owned_video, TRANSCRIBE, explodes)

        error = await pool.fetchval(
            """
            SELECT error FROM pipeline_jobs
            WHERE video_id = $1 AND stage = 'transcribing'::processing_status
            """,
            owned_video,
        )
        assert "injected failure" in error

    async def test_a_failure_never_escapes_the_runner(self, pool, owned_video):
        # A worker that dies on the first bad video stops processing every good
        # one queued behind it.
        await run_step(pool, owned_video, TRANSCRIBE, explodes)

    async def test_each_stage_parks_at_its_own_failure_state(self, pool, owned_video):
        for step, expected in (
            (TRANSCRIBE, "failed_transcribing"),
            (CHUNK, "failed_chunking"),
            (EMBED, "failed_embedding"),
        ):
            await pool.execute(
                "UPDATE videos SET processing_status = $2::processing_status,"
                " retry_count = 0 WHERE id = $1",
                owned_video,
                step.start,
            )
            outcome = await run_step(pool, owned_video, step, explodes, version=99)
            assert outcome == expected, f"{step.name} parked at {outcome}"

    async def test_enrichment_failure_does_not_park_the_video(self, pool, owned_video):
        await pool.execute(
            "UPDATE videos SET processing_status = 'indexed' WHERE id = $1",
            owned_video,
        )

        outcome = await run_step(pool, owned_video, ENRICH, explodes)

        # §11: a chapter-detection failure renders an unsegmented scrubber. The
        # talk stays watchable, searchable, and answerable, so marking it broken
        # would overstate what went wrong.
        assert outcome == "indexed"
        assert await status_of(pool, owned_video) == "indexed"


class TestRetries:
    async def test_requeue_returns_a_parked_video_to_its_start(self, pool, owned_video):
        await run_step(pool, owned_video, TRANSCRIBE, explodes)
        assert await status_of(pool, owned_video) == "failed_transcribing"

        await requeue_failed(pool, max_retries=3)

        assert await status_of(pool, owned_video) == "transcoded"

    async def test_a_video_out_of_retries_stays_parked(self, pool, owned_video):
        for _ in range(3):
            await run_step(pool, owned_video, TRANSCRIBE, explodes)
            await requeue_failed(pool, max_retries=3)

        # Three attempts used. It must stop rather than loop forever.
        assert await retries_of(pool, owned_video) >= 3
        await requeue_failed(pool, max_retries=3)
        assert await status_of(pool, owned_video) == "failed_transcribing"


class TestIdempotency:
    async def test_a_finished_step_is_skipped_on_re_run(self, pool, owned_video):
        await run_step(pool, owned_video, TRANSCRIBE, succeeds)

        calls = {"count": 0}

        async def counted():
            calls["count"] += 1

        outcome = await run_step(pool, owned_video, TRANSCRIBE, counted)

        # §5.1: "The pipeline will be re-run many times during development.
        # Make that free."
        assert outcome == "skipped"
        assert calls["count"] == 0

    async def test_a_crashed_run_is_resumable(self, pool, owned_video):
        """
        A worker killed mid-step leaves a claimed but unfinished job. The next
        run must pick it up rather than skipping it as done.
        """
        await run_step(pool, owned_video, TRANSCRIBE, explodes)
        await requeue_failed(pool)

        calls = {"count": 0}

        async def counted():
            calls["count"] += 1

        await run_step(pool, owned_video, TRANSCRIBE, counted)
        assert calls["count"] == 1

    async def test_attempts_accumulate_on_the_job_row(self, pool, owned_video):
        await run_step(pool, owned_video, TRANSCRIBE, explodes)
        await requeue_failed(pool)
        await run_step(pool, owned_video, TRANSCRIBE, explodes)

        attempts = await pool.fetchval(
            """
            SELECT attempts FROM pipeline_jobs
            WHERE video_id = $1 AND stage = 'transcribing'::processing_status
            """,
            owned_video,
        )
        assert attempts == 2

    async def test_a_new_version_re_runs_the_same_stage(self, pool, owned_video):
        """
        §5.1 keys jobs on (video_id, stage, version). Bumping the version is how
        a model change triggers selective re-indexing without a schema change.
        """
        await run_step(pool, owned_video, TRANSCRIBE, succeeds, version=1)
        await pool.execute(
            "UPDATE videos SET processing_status = 'transcoded' WHERE id = $1",
            owned_video,
        )

        calls = {"count": 0}

        async def counted():
            calls["count"] += 1

        await run_step(pool, owned_video, TRANSCRIBE, counted, version=2)
        assert calls["count"] == 1


class TestEligibility:
    async def test_class_b_never_enters_the_pipeline(self, pool, owned_video):
        rows = await eligible(pool, TRANSCRIBE, limit=500)
        ids = [row["id"] for row in rows]

        classes = await pool.fetch(
            "SELECT DISTINCT source_class::text AS c FROM videos WHERE id = ANY($1::uuid[])",
            ids,
        )
        assert {row["c"] for row in classes} <= {"owned"}

    async def test_only_videos_at_the_step_start_are_eligible(self, pool, owned_video):
        rows = await eligible(pool, CHUNK, limit=500)
        assert owned_video not in [row["id"] for row in rows]

        await pool.execute(
            "UPDATE videos SET processing_status = 'transcribed' WHERE id = $1",
            owned_video,
        )
        rows = await eligible(pool, CHUNK, limit=500)
        assert owned_video in [row["id"] for row in rows]
