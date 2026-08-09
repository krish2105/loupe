from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

from .goldens import CorpusMismatch, assert_corpus_matches, corpus_in_database, load
from .runner import run, summarise, threshold_sweep

"""
Run the evaluation.

    uv run python -m app.run [golden-set.json]

Refuses to score a golden set against a corpus it was not authored for. That
refusal is the point: a benchmark whose numbers compute but do not mean
anything is worse than no benchmark, and there is nothing in the output to
signal it.
"""

DEFAULT_GOLDEN = Path(__file__).resolve().parent.parent / "goldens" / "fixture-v1.json"


async def main() -> int:
    golden_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GOLDEN
    golden = load(golden_path)

    database_url = os.environ.get(
        "DATABASE_URL", "postgres://localhost:5432/loupe_dev"
    ).replace("postgres://", "postgresql://", 1)
    ai_url = os.environ.get("AI_URL", "http://localhost:8031")

    pool = await asyncpg.create_pool(
        database_url, min_size=1, max_size=2, statement_cache_size=0
    )
    try:
        corpus = await corpus_in_database(pool)
        try:
            assert_corpus_matches(golden, corpus)
        except CorpusMismatch as mismatch:
            print(f"REFUSED TO SCORE\n\n{mismatch}\n", file=sys.stderr)
            return 2

        video_id = await pool.fetchval(
            """
            SELECT v.id FROM videos v
            WHERE v.source_class = 'owned'
              AND EXISTS (
                SELECT 1 FROM transcript_chunks c
                WHERE c.video_id = v.id AND c.embedding IS NOT NULL
              )
            ORDER BY v.created_at
            LIMIT 1
            """
        )
    finally:
        await pool.close()

    if video_id is None:
        print("No indexed talk to evaluate against.", file=sys.stderr)
        return 1

    results = await run(golden, ai_url, str(video_id), corpus)

    report = summarise(results)
    report["threshold_sweep"] = threshold_sweep(
        results, [0.34, 0.38, 0.42, 0.46, 0.50, 0.54, 0.58]
    )
    print(json.dumps(report, indent=2))

    # Per-category detail, because an aggregate hides which category failed and
    # the categories test different things.
    by_category: dict[str, list] = {}
    for case in results.cases:
        by_category.setdefault(case.case.category, []).append(case)

    print("\nBy category:", file=sys.stderr)
    for category, cases in sorted(by_category.items()):
        correct = sum(1 for c in cases if c.refused == c.case.should_refuse and not c.error)
        print(f"  {category:15s} {correct}/{len(cases)} decided correctly", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
