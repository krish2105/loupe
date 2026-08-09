from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

"""
The golden set — §11.2.

    "Hand-label 100 question / answer / timestamp triples across 20 videos,
     spanning five categories: factual lookup, cross-video comparison,
     out-of-scope (should refuse), adversarial, and non-English."

Four categories here, not five: §17 decision 3 chose English only, so the
non-English category is dropped and recorded as a limitation.

**A golden set is bound to the corpus it was written against.** Questions were
authored by reading specific transcripts; run them against different
transcripts and every label is wrong while every number still computes. The
`corpus` field records the binding and the runner enforces it, because
"remember not to do that" is not a safeguard.
"""


class CorpusMismatch(RuntimeError):
    """The golden set was written against a different corpus than is loaded."""


@dataclass(frozen=True)
class GoldenCase:
    id: str
    category: str
    question: str
    should_refuse: bool
    video_id: str | None = None
    #: Where a human says the answer is. None for cases that should refuse.
    expected_start_sec: float | None = None
    note: str = ""


@dataclass(frozen=True)
class GoldenSet:
    version: str
    corpus: str
    note: str
    cases: list[GoldenCase]

    def by_category(self) -> dict[str, list[GoldenCase]]:
        grouped: dict[str, list[GoldenCase]] = {}
        for case in self.cases:
            grouped.setdefault(case.category, []).append(case)
        return grouped


def load(path: Path) -> GoldenSet:
    payload = json.loads(path.read_text())

    return GoldenSet(
        version=payload["version"],
        corpus=payload["corpus"],
        note=payload.get("note", ""),
        cases=[
            GoldenCase(
                id=case["id"],
                category=case["category"],
                question=case["question"],
                should_refuse=case["should_refuse"],
                video_id=case.get("video_id"),
                expected_start_sec=case.get("expected_start_sec"),
                note=case.get("note", ""),
            )
            for case in payload["cases"]
        ],
    )


async def corpus_in_database(pool) -> str:
    """
    Which transcription engine produced the transcripts currently loaded.

    Mixed engines are reported as such rather than resolved to one — a set
    scored against half-fixture, half-real transcripts is not scoreable, and
    silently picking the majority would hide that.
    """
    rows = await pool.fetch("SELECT DISTINCT engine FROM transcripts")
    engines = sorted(row["engine"] for row in rows)

    if not engines:
        return "empty"
    if len(engines) > 1:
        return "mixed:" + "+".join(engines)
    return engines[0]


def assert_corpus_matches(golden: GoldenSet, actual: str) -> None:
    """
    Refuse to score a golden set against the wrong corpus.

    This is the safeguard that stops the most damaging thing this repository
    could produce: a benchmark table whose numbers are arithmetically correct
    and mean nothing. Every label in a golden set encodes a claim about a
    specific transcript, and nothing about a mismatched run looks wrong.
    """
    if golden.corpus != actual:
        raise CorpusMismatch(
            f"golden set {golden.version!r} was authored against corpus "
            f"{golden.corpus!r}, but the database holds {actual!r}. "
            "Every label in the set encodes a claim about specific transcripts, "
            "so scoring it here would produce numbers that compute and mean "
            "nothing. Re-label against the current corpus."
        )
