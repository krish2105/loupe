from __future__ import annotations

import math
from dataclasses import dataclass

"""
Chapter detection — §10.2.

    "Two-stage: cosine drift between consecutive windows finds boundaries; an
     LLM names them. Not a single prompt."

The two-stage split is the whole point. Asking a model to read a transcript and
return chapters produces plausible chapters that do not correspond to anything
measurable, and there is no way to tell a good answer from a confident one.
Finding boundaries from embedding drift is a measurement — it is reproducible,
it has a confidence value, and it fails visibly. The model is then given a
bounded job it is actually good at: naming a span of text it can see.

§11's failure mode for chapters is "render an unsegmented scrubber", so low
confidence returns nothing rather than guessing.
"""

# A window of one chunk is too noisy — a single tangent reads as a topic change.
WINDOW = 2

# Drift above this is a candidate boundary. Tuned to be conservative: a missed
# chapter is invisible, a wrong one is a scrubber segment that lies.
DRIFT_THRESHOLD = 0.22

# Chapters shorter than this are not useful to click on.
MIN_CHAPTER_SECONDS = 45.0


@dataclass(frozen=True)
class Boundary:
    chunk_index: int
    start_sec: float
    drift: float


@dataclass(frozen=True)
class Chapter:
    index: int
    start_sec: float
    end_sec: float
    title: str
    confidence: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    count = len(vectors)
    return [sum(values) / count for values in zip(*vectors, strict=True)]


def find_boundaries(
    embeddings: list[list[float]],
    starts: list[float],
    *,
    window: int = WINDOW,
    threshold: float = DRIFT_THRESHOLD,
    min_seconds: float = MIN_CHAPTER_SECONDS,
) -> list[Boundary]:
    """
    Stage one: where does the subject change?

    Compares the mean embedding of the `window` chunks before a position with
    the `window` chunks after it. A large drop in similarity is a topic shift.
    """
    if len(embeddings) < window * 2 + 1:
        return []

    candidates: list[Boundary] = []
    for position in range(window, len(embeddings) - window + 1):
        before = _mean_vector(embeddings[position - window : position])
        after = _mean_vector(embeddings[position : position + window])
        drift = 1.0 - cosine_similarity(before, after)

        if drift >= threshold:
            candidates.append(Boundary(position, starts[position], drift))

    # Keep only the strongest boundary in any neighbourhood. Adjacent positions
    # both detect the same shift, and two chapters starting three seconds apart
    # is worse than one.
    chosen: list[Boundary] = []
    for candidate in sorted(candidates, key=lambda b: b.drift, reverse=True):
        if all(
            abs(candidate.start_sec - kept.start_sec) >= min_seconds
            for kept in chosen
        ):
            chosen.append(candidate)

    return sorted(chosen, key=lambda b: b.start_sec)


def build_chapters(
    boundaries: list[Boundary],
    total_duration: float,
    titles: list[str],
) -> list[Chapter]:
    """
    Stage two, assembled: boundaries plus the names the model gave them.

    The first chapter always starts at zero — a talk does not begin at its
    first topic shift.
    """
    if not boundaries:
        return []

    starts = [0.0] + [b.start_sec for b in boundaries]
    drifts = [boundaries[0].drift] + [b.drift for b in boundaries]

    chapters: list[Chapter] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else total_duration
        if end <= start:
            continue

        chapters.append(
            Chapter(
                index=len(chapters),
                start_sec=start,
                end_sec=end,
                title=titles[index] if index < len(titles) else f"Part {index + 1}",
                # Drift is a distance, not a probability. Reporting it directly
                # as confidence would overstate it, so it is squashed into a
                # bounded score and stored for §11's low-confidence fallback.
                confidence=min(1.0, drifts[index] / (DRIFT_THRESHOLD * 2)),
            )
        )

    return chapters
