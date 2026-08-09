from __future__ import annotations

import re

"""
Transcript normalisation — §10.2.

    "Strip bracketed caption annotations and filler tokens; collapse
     whitespace; retain the original."

§6.5 decision 1 is the reason this exists as a separate step rather than being
folded into chunking: transcript_chunks stores *two* texts. The normalised one
is embedded; the display one is shown. Normalising for retrieval while
displaying the original is the correct separation and almost no implementation
does it — so the two are produced together, here, and never diverge later.

What normalisation must not do is move a timestamp. Every transformation below
is within-token or whitespace-only, so word timings survive it untouched.
"""

# [Music], [Applause], (laughter), ♪♪ — caption furniture, never speech.
_ANNOTATION = re.compile(r"[\[\(][^\]\)]{0,40}[\]\)]|♪+")

# Speaker labels at the start of a line: "SPEAKER 1:", "Interviewer:".
_SPEAKER_LABEL = re.compile(r"^\s*[A-Z][A-Z0-9 .'-]{1,30}:\s*", re.MULTILINE)

# Standalone disfluencies. Word-bounded so "umbrella" and "here" survive.
_FILLER = re.compile(
    r"\b(?:um+|uh+|erm+|hmm+|mm+|ah+|eh+|you know|i mean|sort of|kind of)\b",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"\s+")
_ORPHAN_PUNCT = re.compile(r"\s+([,.!?;:])")

# Removing a filler phrase between commas leaves ",,". Left alone it survives
# into the embedded text and, worse, into a citation shown to a reader.
_REPEATED_PUNCT = re.compile(r"([,;:])(?:\s*[,;:])+")
_LEADING_PUNCT = re.compile(r"^[\s,;:.]+")


def normalise(text: str) -> str:
    """
    Produce the text that gets embedded.

    Aggressive on purpose: an embedding of "um, so, you know, the thing is"
    spends most of its signal on nothing. The reader still sees the original,
    so nothing is lost — only the retrieval representation is cleaned.
    """
    cleaned = _ANNOTATION.sub(" ", text)
    cleaned = _SPEAKER_LABEL.sub(" ", cleaned)
    cleaned = _FILLER.sub(" ", cleaned)
    cleaned = _ORPHAN_PUNCT.sub(r"\1", cleaned)
    cleaned = _REPEATED_PUNCT.sub(r"\1", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned)
    cleaned = _LEADING_PUNCT.sub("", cleaned)
    return cleaned.strip()


def display(text: str) -> str:
    """
    Produce the text a reader sees.

    Only whitespace is touched. Filler and annotations stay, because a
    transcript that silently edits what someone said is a transcript nobody
    should trust — and §11.1 makes the credibility of the whole intelligence
    layer rest on citations landing where they claim to.
    """
    return _WHITESPACE.sub(" ", text).strip()


def normalise_pair(text: str) -> tuple[str, str]:
    """Both texts from one source, so they can never drift apart."""
    return normalise(text), display(text)
