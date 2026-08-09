from __future__ import annotations

import re
from dataclasses import dataclass

"""
Evaluation metrics — §11.2.

    "Metrics published: retrieval precision@5 · citation timestamp accuracy
     within ±5s · answer faithfulness · refusal accuracy."

These are pure functions with their own tests, and that is not fussiness. A
metric implementation is the one piece of code whose bugs are invisible: it
produces a plausible number either way, the number goes in a README, and
nobody can tell it is wrong by looking at it. A wrong retrieval system is
noticed; a wrong precision@5 is published.

So every metric here is tested against cases where the correct answer is known
by hand.
"""

#: §11.2's tolerance. A citation is correct if it lands within five seconds of
#: the moment a human said it does.
#:
#: A band rather than an exact match, deliberately: the "right" moment for a
#: statement is itself fuzzy — a labeller marking where an idea begins will
#: disagree with themselves by a second or two on a second pass. Demanding
#: exactness would measure labeller precision, not system accuracy.
TIMESTAMP_TOLERANCE_SEC = 5.0


@dataclass(frozen=True)
class RefusalCounts:
    """A confusion matrix for the refuse/answer decision."""

    true_refusals: int = 0  # should refuse, did refuse
    false_refusals: int = 0  # should answer, refused
    true_answers: int = 0  # should answer, answered
    false_answers: int = 0  # should refuse, answered — the dangerous one

    @property
    def total(self) -> int:
        return (
            self.true_refusals
            + self.false_refusals
            + self.true_answers
            + self.false_answers
        )

    @property
    def accuracy(self) -> float:
        return (self.true_refusals + self.true_answers) / self.total if self.total else 0.0

    @property
    def false_answer_rate(self) -> float:
        """
        How often the system answered something it should have refused.

        §11.1 calls this the failure mode that gets noticed in a demo. It is
        reported separately from accuracy because accuracy hides it: a system
        that answers everything scores well on a golden set that is mostly
        answerable, while doing the one thing that discredits it.
        """
        should_refuse = self.true_refusals + self.false_answers
        return self.false_answers / should_refuse if should_refuse else 0.0

    @property
    def refusal_rate(self) -> float:
        """§11.1 tracks this as a headline metric — a feature, not a defect."""
        refused = self.true_refusals + self.false_refusals
        return refused / self.total if self.total else 0.0


def precision_at_k(retrieved: list[str], relevant: set[str], k: int = 5) -> float:
    """
    Fraction of the top k retrieved items that are relevant.

    Divided by k rather than by len(retrieved), so a system that returns two
    results and gets both right does not score the same as one that returns
    five and gets all five. Padding a short result list to look precise is the
    exact behaviour this should not reward.
    """
    if k <= 0:
        return 0.0
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for item in top if item in relevant) / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int = 5) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def timestamp_hit(
    predicted_sec: float | None,
    expected_sec: float,
    tolerance: float = TIMESTAMP_TOLERANCE_SEC,
) -> bool:
    """
    Did the citation land on the moment?

    §11.1: "If a timestamp lands on the wrong moment, the entire intelligence
    layer loses credibility instantly."
    """
    if predicted_sec is None:
        return False
    return abs(predicted_sec - expected_sec) <= tolerance


def best_timestamp_hit(
    predicted: list[float], expected_sec: float, tolerance: float = TIMESTAMP_TOLERANCE_SEC
) -> bool:
    """
    An answer carries 1–4 citations. It counts as correct if *any* of them
    lands on the moment, because the reader clicks the right one.

    The alternative — requiring the first citation to be correct — would
    measure ranking rather than citation accuracy, which is a different claim.
    """
    return any(timestamp_hit(value, expected_sec, tolerance) for value in predicted)


_SENTENCE = re.compile(r"[.!?]+\s+")
_NORMALISE = re.compile(r"[^a-z0-9 ]+")


def _tokens(text: str) -> set[str]:
    return set(_NORMALISE.sub(" ", text.lower()).split())


def faithfulness(answer: str, sources: list[str]) -> float:
    """
    What fraction of the answer is supported by the cited passages.

    Lexical overlap per sentence, which is a weak proxy for a generative
    answerer and an exact measurement for an extractive one — an extractive
    answer scores 1.0 by construction, and any drop means it started
    paraphrasing, which is the regression worth catching.

    §11.2's note applies here: an LLM judge would score this better and carries
    published biases. When one is used it must be pinned and reported, and this
    lexical score kept alongside as the reproducible floor.
    """
    if not answer.strip():
        return 0.0
    if not sources:
        return 0.0

    supported_tokens = set()
    for source in sources:
        supported_tokens |= _tokens(source)

    sentences = [part for part in _SENTENCE.split(answer) if part.strip()]
    if not sentences:
        return 0.0

    scores = []
    for sentence in sentences:
        tokens = _tokens(sentence)
        if not tokens:
            continue
        scores.append(len(tokens & supported_tokens) / len(tokens))

    return sum(scores) / len(scores) if scores else 0.0


def tally_refusals(cases: list[tuple[bool, bool]]) -> RefusalCounts:
    """
    Build the confusion matrix from (should_refuse, did_refuse) pairs.
    """
    counts = {"tr": 0, "fr": 0, "ta": 0, "fa": 0}
    for should_refuse, did_refuse in cases:
        if should_refuse and did_refuse:
            counts["tr"] += 1
        elif should_refuse and not did_refuse:
            counts["fa"] += 1
        elif not should_refuse and did_refuse:
            counts["fr"] += 1
        else:
            counts["ta"] += 1

    return RefusalCounts(
        true_refusals=counts["tr"],
        false_refusals=counts["fr"],
        true_answers=counts["ta"],
        false_answers=counts["fa"],
    )


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
