from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .goldens import GoldenCase, GoldenSet
from .metrics import (
    TIMESTAMP_TOLERANCE_SEC,
    RefusalCounts,
    best_timestamp_hit,
    faithfulness,
    mean,
    tally_refusals,
)

"""
The runner.

Asks every golden question of the live AI service and scores the answers. It
does not call retrieval directly: the thing being measured is the system a
person actually uses, including the refusal threshold, the citation selection,
and the answerer — measuring the parts separately would score something nobody
runs.
"""


@dataclass
class CaseResult:
    case: GoldenCase
    refused: bool
    answer: str
    citation_starts: list[float]
    citation_texts: list[str]
    top_score: float
    error: str | None = None

    @property
    def timestamp_hit(self) -> bool | None:
        """None when the case has no timestamp to check — refusals do not."""
        if self.case.expected_start_sec is None:
            return None
        return best_timestamp_hit(self.citation_starts, self.case.expected_start_sec)


@dataclass
class Results:
    golden_version: str
    corpus: str
    model: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def refusal_counts(self) -> RefusalCounts:
        return tally_refusals(
            [(case.case.should_refuse, case.refused) for case in self.cases if not case.error]
        )

    @property
    def timestamp_accuracy(self) -> float | None:
        """
        Over the cases that have a labelled timestamp *and* were answered.

        A refused case has no citation to check, so counting it would conflate
        two different failures — refusing wrongly is already measured by
        refusal accuracy, and double-counting it here would hide a genuine
        citation problem behind a refusal problem.
        """
        checked = [
            case.timestamp_hit
            for case in self.cases
            if case.timestamp_hit is not None and not case.refused and not case.error
        ]
        return mean([1.0 if hit else 0.0 for hit in checked]) if checked else None

    @property
    def faithfulness(self) -> float | None:
        scored = [
            faithfulness(case.answer, case.citation_texts)
            for case in self.cases
            if not case.refused and not case.error and case.citation_texts
        ]
        return mean(scored) if scored else None

    @property
    def answered_cases(self) -> int:
        return sum(1 for case in self.cases if not case.refused and not case.error)

    @property
    def errors(self) -> int:
        return sum(1 for case in self.cases if case.error)


async def ask_one(
    client: httpx.AsyncClient, base_url: str, video_id: str, case: GoldenCase
) -> CaseResult:
    try:
        response = await client.post(
            f"{base_url}/v1/videos/{case.video_id or video_id}/ask",
            json={"question": case.question},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as error:  # noqa: BLE001 - one bad case must not end the run
        return CaseResult(
            case=case,
            refused=False,
            answer="",
            citation_starts=[],
            citation_texts=[],
            top_score=0.0,
            error=repr(error),
        )

    citations = payload.get("citations", [])
    return CaseResult(
        case=case,
        refused=bool(payload.get("refused")),
        answer=payload.get("answer", ""),
        citation_starts=[float(c["start_sec"]) for c in citations],
        citation_texts=[c["text"] for c in citations],
        top_score=float(payload.get("top_score", 0.0)),
    )


async def run(
    golden: GoldenSet, base_url: str, default_video_id: str, corpus: str
) -> Results:
    async with httpx.AsyncClient() as client:
        health = await client.get(f"{base_url}/health", timeout=30)
        model = health.json().get("answerer", "unknown")

        results = Results(golden_version=golden.version, corpus=corpus, model=model)
        for case in golden.cases:
            results.cases.append(await ask_one(client, base_url, default_video_id, case))

    return results


def threshold_sweep(results: Results, candidates: list[float]) -> list[dict]:
    """
    What the refusal decision *would* have been at other thresholds.

    Recomputed from the recorded top scores, so it costs nothing and needs no
    re-run. This is analysis, not tuning: §11.2 warns that a golden set must
    stay stable, and picking whichever threshold maximises a 24-case fixture
    score is overfitting to the fixture, not tuning the system.

    It is published so the trade-off is visible — raising the threshold buys
    fewer false answers at the price of false refusals, and there is no value
    that makes both zero.
    """
    sweep = []
    for threshold in candidates:
        counts = tally_refusals(
            [
                (case.case.should_refuse, case.top_score < threshold)
                for case in results.cases
                if not case.error
            ]
        )
        sweep.append(
            {
                "threshold": threshold,
                "accuracy": round(counts.accuracy, 4),
                "false_answers": counts.false_answers,
                "false_refusals": counts.false_refusals,
                "false_answer_rate": round(counts.false_answer_rate, 4),
            }
        )
    return sweep


def summarise(results: Results) -> dict:
    counts = results.refusal_counts

    return {
        "golden_set": results.golden_version,
        "corpus": results.corpus,
        "answerer": results.model,
        "cases": len(results.cases),
        "errors": results.errors,
        "timestamp_tolerance_sec": TIMESTAMP_TOLERANCE_SEC,
        "refusal": {
            "accuracy": round(counts.accuracy, 4),
            "refusal_rate": round(counts.refusal_rate, 4),
            "false_answer_rate": round(counts.false_answer_rate, 4),
            "true_refusals": counts.true_refusals,
            "false_refusals": counts.false_refusals,
            "true_answers": counts.true_answers,
            "false_answers": counts.false_answers,
        },
        "citation_timestamp_accuracy": (
            round(results.timestamp_accuracy, 4)
            if results.timestamp_accuracy is not None
            else None
        ),
        "faithfulness_lexical": (
            round(results.faithfulness, 4) if results.faithfulness is not None else None
        ),
        "answered": results.answered_cases,
    }
