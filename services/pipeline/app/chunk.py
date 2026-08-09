from __future__ import annotations

from dataclasses import dataclass

from .normalise import normalise_pair

"""
Chunking — §10.2.

    "300–600 token chunks, ~50 token overlap. Split on natural pauses and topic
     shifts, never fixed windows. Every chunk carries video_id, start_sec,
     end_sec, speaker."

Fixed windows are the default everywhere and they are wrong here for a specific
reason: a window boundary lands mid-sentence roughly always, which means the
one chunk containing the answer to a question often contains half of it. §11.1
makes the entire intelligence layer's credibility rest on a citation landing on
the right moment, and a chunk that starts mid-clause cannot do that.

So boundaries are chosen, in order of preference:
  1. a long pause — the speaker stopped, which is where meaning breaks
  2. a sentence end
  3. the token budget, as a last resort

Timestamps are never flattened. Each chunk keeps the real start of its first
word and the real end of its last.
"""

# A pause this long is a paragraph break in speech.
PAUSE_SECONDS = 0.65

MIN_TOKENS = 300
MAX_TOKENS = 600
OVERLAP_TOKENS = 50

_SENTENCE_END = (".", "?", "!")


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    speaker: str | None = None


@dataclass(frozen=True)
class Chunk:
    index: int
    start_sec: float
    end_sec: float
    speaker: str | None
    text_normalised: str
    text_display: str
    token_count: int


def _is_boundary(words: list[Word], position: int) -> bool:
    """A pause before this word, or a sentence ending at the previous one."""
    if position <= 0 or position >= len(words):
        return False

    previous, current = words[position - 1], words[position]
    if current.start - previous.end >= PAUSE_SECONDS:
        return True
    return previous.text.endswith(_SENTENCE_END)


def _choose_end(words: list[Word], start: int) -> int:
    """
    The exclusive end index for a chunk beginning at `start`.

    Looks for the last natural boundary inside the acceptable band. Falls back
    to MAX_TOKENS only when the speaker genuinely did not pause — which happens,
    and is the one case where a hard cut is the honest answer.
    """
    hard_limit = min(start + MAX_TOKENS, len(words))
    soft_floor = min(start + MIN_TOKENS, len(words))

    if hard_limit >= len(words):
        return len(words)

    best = None
    for position in range(soft_floor, hard_limit + 1):
        if _is_boundary(words, position):
            best = position

    return best or hard_limit


def chunk_words(words: list[Word]) -> list[Chunk]:
    """Split a word-level transcript into overlapping, boundary-aligned chunks."""
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0

    while start < len(words):
        end = _choose_end(words, start)
        window = words[start:end]
        if not window:
            break

        raw = " ".join(word.text for word in window)
        text_normalised, text_display = normalise_pair(raw)

        # A window that normalises to nothing — pure applause, say — carries no
        # retrievable signal, and an embedding of an empty string is noise that
        # will match everything weakly.
        if text_normalised:
            speakers = {word.speaker for word in window if word.speaker}
            chunks.append(
                Chunk(
                    index=len(chunks),
                    start_sec=window[0].start,
                    end_sec=window[-1].end,
                    # A chunk spanning two speakers belongs to neither.
                    speaker=speakers.pop() if len(speakers) == 1 else None,
                    text_normalised=text_normalised,
                    text_display=text_display,
                    token_count=len(window),
                )
            )

        if end >= len(words):
            break

        # Overlap so a sentence straddling a boundary is retrievable from both
        # sides. Always advance, or a short final window loops forever.
        start = max(start + 1, end - OVERLAP_TOKENS)

    return chunks
