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
    """
    The opening sentences of a passage, deduplicated and starting like a
    sentence.

    Two corrections, both from reading the output on the video page rather than
    from a test.

    Repeats are dropped. A speaker restating a point is normal, and a chunk that
    happens to span the restatement produced a TL;DR reading "we store the keys
    across decoding steps. paged attention removes the contiguous allocation
    requirement. we store the keys across decoding steps." Three sentences by
    the contract's count, one sentence of information.

    The first letter is capitalised. Chunks split on pauses and overlap by
    roughly fifty tokens, so a passage frequently starts mid-sentence. That is
    correct for retrieval and reads as broken when it becomes the first thing
    on the page.
    """
    seen: set[str] = set()
    kept: list[str] = []

    for part in _SENTENCE.split(text.strip()):
        sentence = part.strip()
        if not sentence:
            continue

        key = " ".join(sentence.lower().split())
        if key in seen:
            continue

        seen.add(key)
        kept.append(sentence)
        if len(kept) == count:
            break

    if not kept:
        return ""

    joined = " ".join(kept)
    return joined[0].upper() + joined[1:]


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

    # Two buckets can land on the same sentence when a speaker returns to a
    # point. Five key points where two are identical is a worse summary than
    # four distinct ones, so the duplicate is dropped rather than replaced with
    # the next-best passage from that fifth: the next-best is chosen for score,
    # not for saying something new, and padding to five is how a summary starts
    # containing filler. Same judgement as the playlist floor.
    key_points: list[KeyPoint] = []
    said: set[str] = set()

    for index in sorted(set(chosen)):
        text = first_sentences(texts[index], 1) or texts[index][:200]
        key = " ".join(text.lower().split())
        if key in said:
            continue
        said.add(key)
        key_points.append(KeyPoint(text=text, start_sec=starts[index]))

    if len(key_points) < 2:
        return None

    # The TL;DR comes from the single most central passage, capped at three
    # sentences by the contract.
    most_central = max(scored, key=lambda item: item[1])[0]
    tldr = first_sentences(texts[most_central], TLDR_SENTENCES)
    if not tldr:
        return None

    return Summary(tldr=tldr, key_points=key_points, model=model)
