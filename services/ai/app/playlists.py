from __future__ import annotations

from dataclasses import dataclass

from .retrieval import CITATION_THRESHOLD, RetrievedChunk

"""
AI playlists — §11.

    Input:    a natural-language brief.
    Output:   an ordered list plus a written rationale for the ordering.
    Failure:  return fewer items rather than padding with poor matches.
    Cache:    saved as a real playlist.

The failure clause is the whole design. A playlist endpoint that always returns
ten talks is a search results page wearing a hat — the tenth result exists
because the loop asked for ten, not because it belongs. So there is a floor, a
brief that clears it for two talks produces a playlist of two, and a brief that
clears it for none produces a refusal.

Composition is retrieval plus ordering. No model is called and no tokens are
spent, which is why this sits outside the §10.3 cost ceiling entirely.
"""

#: How related a talk's best moment must be to the brief to earn a place.
#:
#: This started as CITATION_THRESHOLD (0.34), on the reasoning that "related
#: enough to cite" and "related enough to include" are the same question. That
#: was wrong, and measurably so. Composing against the indexed corpus:
#:
#:     "how attention scales with sequence length"   → 0.644 – 0.649
#:     "making inference cheap enough to deploy"     → 0.493 – 0.505
#:     "underwater basket weaving for beginners"     → 0.363 – 0.372
#:
#: The third brief cleared 0.34 comfortably and produced a full eight-talk
#: playlist of MLSys talks. bge-m3 puts unrelated text around 0.35, so any
#: absolute threshold down there is inside the model's noise floor and cannot
#: separate "about this" from "not about this" at all.
#:
#: Set above that floor so the off-topic case refuses. Calibrated against three
#: briefs on an eight-video corpus, which is thin enough that it is recorded as
#: provisional rather than presented as tuned — see docs/ai-playlists.md. The
#: separation it relies on (0.37 against 0.49) is wide; the confidence that the
#: boundary sits in the right place within that gap is not.
INCLUSION_FLOOR = 0.45

# Kept as an import so the relationship stays visible: this constant used to be
# that one, and the docstring above is the record of why it no longer is.
_BORROWED_FROM = CITATION_THRESHOLD

#: Fewer than this is not a playlist, it is a search result. Refuse instead.
MIN_ITEMS = 3

MAX_ITEMS = 12


@dataclass(frozen=True)
class VideoCard:
    video_id: str
    title: str
    channel_id: str
    channel_name: str


@dataclass(frozen=True)
class PlaylistItem:
    video_id: str
    title: str
    channel_name: str
    #: Where in the talk the brief is actually addressed. This is the reason to
    #: build the feature on the transcript layer instead of on titles.
    start_sec: float
    excerpt: str
    score: float


@dataclass(frozen=True)
class PlaylistProposal:
    title: str
    items: tuple[PlaylistItem, ...]
    rationale: str
    refused: bool
    reason: str | None = None


def compose(
    brief: str,
    chunks: list[RetrievedChunk],
    cards: dict[str, VideoCard],
    *,
    limit: int = 8,
) -> PlaylistProposal:
    """
    Turn a brief and its retrieved moments into an ordered playlist.

    `chunks` is expected to be one best chunk per video, already sorted by
    similarity — which is what search_across_catalogue returns.
    """
    limit = max(MIN_ITEMS, min(limit, MAX_ITEMS))

    eligible = [
        chunk
        for chunk in chunks
        if chunk.similarity >= INCLUSION_FLOOR and chunk.video_id in cards
    ]

    if len(eligible) < MIN_ITEMS:
        return PlaylistProposal(
            title=_title_for(brief),
            items=(),
            rationale="",
            refused=True,
            reason=(
                "Not enough talks in the catalogue address this closely enough "
                "to make a playlist worth watching."
            ),
        )

    ordered = _spread_channels(eligible, cards)[:limit]

    items = tuple(
        PlaylistItem(
            video_id=chunk.video_id,
            title=cards[chunk.video_id].title,
            channel_name=cards[chunk.video_id].channel_name,
            start_sec=chunk.start_sec,
            excerpt=_excerpt(chunk.text_display),
            score=round(chunk.similarity, 4),
        )
        for chunk in ordered
    )

    return PlaylistProposal(
        title=_title_for(brief),
        items=items,
        rationale=write_rationale(brief, items),
        refused=False,
    )


def _spread_channels(
    chunks: list[RetrievedChunk], cards: dict[str, VideoCard]
) -> list[RetrievedChunk]:
    """
    Take the best talk from each channel before taking anyone's second.

    Without this a brief about scaling laws returns six talks from whichever
    conference happened to run a scaling track, which is a worse answer to the
    brief even though every item individually scores well. Same reasoning as the
    diversity term in §12.1, applied to a list rather than a feed.

    Relative order within a round is preserved, so the strongest match is still
    first.
    """
    by_channel: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        by_channel.setdefault(cards[chunk.video_id].channel_id, []).append(chunk)

    spread: list[RetrievedChunk] = []
    round_index = 0
    while any(len(queue) > round_index for queue in by_channel.values()):
        for queue in by_channel.values():
            if len(queue) > round_index:
                spread.append(queue[round_index])
        round_index += 1

    # Each round is re-sorted, not the whole list: round one holds every
    # channel's best talk and should lead with the strongest of them, but a
    # channel's second talk must never outrank another channel's first.
    result: list[RetrievedChunk] = []
    start = 0
    for round_number in range(round_index):
        size = sum(1 for queue in by_channel.values() if len(queue) > round_number)
        chunk_round = spread[start : start + size]
        result.extend(sorted(chunk_round, key=lambda c: c.similarity, reverse=True))
        start += size

    return result


def write_rationale(brief: str, items: tuple[PlaylistItem, ...]) -> str:
    """
    The written rationale §11 requires, assembled from what actually happened.

    Templated rather than generated, and that is a decision rather than a
    shortcut. A model asked to explain this ordering would produce a fluent
    paragraph about pedagogical progression that describes an ordering nobody
    computed — the single most embarrassing failure available to this feature,
    because the rationale is the part a reader trusts.

    Every number below is read off the result.
    """
    if not items:
        return ""

    channels = {item.channel_name for item in items}
    strongest = items[0]
    weakest = min(items, key=lambda item: item.score)

    ordering = (
        "Ordered by how directly each talk addresses the brief, strongest "
        "first, with one talk from each channel before any channel's second."
    )

    return (
        f"{len(items)} talks from {len(channels)} "
        f"{'channel' if len(channels) == 1 else 'channels'}, "
        f"chosen by searching transcripts for “{brief}” rather than titles. "
        f"{ordering} "
        f"Match strength runs from {strongest.score:.2f} down to "
        f"{weakest.score:.2f}; anything below {INCLUSION_FLOOR:.2f} was left "
        f"out rather than padding the list. Each talk opens at the moment the "
        f"transcript addresses the brief."
    )


def _title_for(brief: str) -> str:
    cleaned = " ".join(brief.split()).rstrip("?.")
    if not cleaned:
        return "Composed playlist"
    title = cleaned[:1].upper() + cleaned[1:]
    return title[:80]


def _excerpt(text: str, words: int = 28) -> str:
    parts = text.split()
    if len(parts) <= words:
        return text
    return " ".join(parts[:words]) + "…"


__all__ = [
    "INCLUSION_FLOOR",
    "MAX_ITEMS",
    "MIN_ITEMS",
    "PlaylistItem",
    "PlaylistProposal",
    "VideoCard",
    "compose",
    "write_rationale",
]
