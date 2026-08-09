from __future__ import annotations

import math
import re
from dataclasses import dataclass

"""
Summarising — §11's contract.

    Output: TL;DR (≤3 sentences) plus 5 key points, each with start_sec
    Failure: hide the block. Never show a partial summary
    Cache: permanent, invalidated on re-transcription

The key points carrying a start_sec is the part that matters. A summary you can
read is ordinary; a summary where every point is a place you can jump to is the
product. So the timestamp is not decoration on the output — it is the reason
each point was selected from a chunk rather than written freely.

Extractive, for the same reason as answering: every sentence is one the speaker
said. A generative summariser plugs in behind the same shape when a key exists.
"""

_SENTENCE = re.compile(r"(?<=[.!?])\s+")

KEY_POINTS = 5
TLDR_SENTENCES = 3


@dataclass(frozen=True)
class KeyPoint:
    text: str
    start_sec: float


@dataclass(frozen=True)
class Summary:
    tldr: str
    key_points: list[KeyPoint]
    model: str


def first_sentences(text: str, count: int) -> str:
    parts = [part.strip() for part in _SENTENCE.split(text.strip()) if part.strip()]
    return " ".join(parts[:count])


def _centroid(vectors: list[list[float]]) -> list[float]:
    total = len(vectors)
    return [sum(values) / total for values in zip(*vectors, strict=True)]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0



def summarise(
    texts: list[str],
    starts: list[float],
    embeddings: list[list[float]],
    model: str = "extractive-v1",
) -> Summary | None:
    """
    Pick the passages most representative of the talk, spread across it.

    Two constraints, and the second is what stops this being useless:

    1. Representative — closest to the talk's centroid, so a tangent is not
       mistaken for a main point.
    2. Spread — one point per fifth of the talk. Without this, all five key
       points come from wherever the speaker was most on-topic, which is
       usually the first ten minutes, and the summary silently describes only
       the opening.

    Returns None rather than a partial summary when there is too little to work
    with. §11: "Hide the block. Never show a partial summary."
    """
    if len(texts) < KEY_POINTS or len(texts) != len(embeddings):
        return None

    centre = _centroid(embeddings)
    scored = [
        (index, _cosine(embeddings[index], centre)) for index in range(len(texts))
    ]

    # One representative passage per fifth of the talk.
    bucket_size = max(1, len(texts) // KEY_POINTS)
    chosen: list[int] = []
    for bucket in range(KEY_POINTS):
        lower = bucket * bucket_size
        upper = len(texts) if bucket == KEY_POINTS - 1 else (bucket + 1) * bucket_size
        window = [item for item in scored if lower <= item[0] < upper]
        if window:
            chosen.append(max(window, key=lambda item: item[1])[0])

    if len(chosen) < 2:
        return None

    key_points = [
        KeyPoint(text=first_sentences(texts[index], 1) or texts[index][:200],
                 start_sec=starts[index])
        for index in sorted(set(chosen))
    ]

    # The TL;DR comes from the single most central passage, capped at three
    # sentences by the contract.
    most_central = max(scored, key=lambda item: item[1])[0]
    tldr = first_sentences(texts[most_central], TLDR_SENTENCES)
    if not tldr:
        return None

    return Summary(tldr=tldr, key_points=key_points, model=model)
