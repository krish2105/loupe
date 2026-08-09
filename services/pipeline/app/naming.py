from __future__ import annotations

import re
from collections import Counter

"""
Chapter naming — stage two of §10.2.

§5 puts all prompts and model routing in the AI service, not here. The pipeline
therefore *measures* boundaries and delegates naming; when the AI service
exists in Phase 6, this is the seam it plugs into.

Until then a heuristic namer runs. It is not pretending to be a model: it picks
the terms that distinguish a span from the rest of the talk, which produces
honest labels like "memory bandwidth, roofline" rather than invented prose. A
label that reads as machine-written is better than one that reads as authored
and is not.
"""

_TOKEN = re.compile(r"[a-z][a-z'-]{2,}")

_STOPWORDS = frozenset(
    """the and that with this you for are was were have has had not but they them
    their there here what when where which who whom how why all any can will would
    could should from into over under about after before then than very just also
    more most some such only own same too its it's our your his her out off down
    thing things going want really actually basically going get got know think
    like one two three lot bit way now say said says talk talking see look
    """.split()
)


def _terms(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 3
    ]


class HeuristicNamer:
    """Distinctive-term naming. Deterministic, offline, and obviously mechanical."""

    name = "heuristic-v1"

    def title_for(self, span_text: str, corpus_text: str) -> str:
        """
        The terms this span uses far more than the talk as a whole.

        A plain frequency count would return the talk's overall subject for
        every chapter, which is how naïve keyword titling produces six chapters
        all called "the model".
        """
        span_counts = Counter(_terms(span_text))
        if not span_counts:
            return "Untitled section"

        corpus_counts = Counter(_terms(corpus_text))
        corpus_total = max(1, sum(corpus_counts.values()))
        span_total = max(1, sum(span_counts.values()))

        scored = {
            term: (count / span_total) / ((corpus_counts[term] / corpus_total) or 1e-6)
            for term, count in span_counts.items()
            if count >= 2
        }
        if not scored:
            scored = {term: float(count) for term, count in span_counts.items()}

        best = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:3]
        return ", ".join(term for term, _ in best).capitalize()


class AiServiceNamer:  # pragma: no cover - Phase 6
    """
    Placeholder for the §5 boundary.

    Naming is a prompt, and prompts belong to the AI service. When it exists,
    this calls it; the pipeline still never holds a model key.
    """

    name = "ai-service"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def title_for(self, span_text: str, corpus_text: str) -> str:
        raise NotImplementedError("The AI service arrives in Phase 6.")
