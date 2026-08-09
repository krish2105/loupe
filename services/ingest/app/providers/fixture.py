from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from .base import ExternalChannel, ExternalVideo, Page

"""
The fixture provider.

Stands in for the Data API when no key is configured. It is deterministic —
the same handle always yields the same channel and the same videos — so
re-running the sync is genuinely idempotent rather than accidentally so, and
the ingest path can be tested end to end without a network.

Everything it produces is clearly fixture content and is labelled as such in
the README. It is not presented as a real catalogue.
"""

TOPICS = [
    "Scaling laws in practice",
    "Attention without the quadratic cost",
    "KV cache management at serving time",
    "Speculative decoding tradeoffs",
    "Mixture-of-experts routing",
    "Quantisation and where accuracy breaks",
    "Distributed training beyond one node",
    "Retrieval that survives production",
    "Evaluating generation honestly",
    "Long-context attention patterns",
    "Optimiser behaviour at scale",
    "Data curation for pretraining",
    "Inference on commodity hardware",
    "Learning from human feedback",
    "Structured and constrained decoding",
    "Vector index tradeoffs",
    "Streaming and online learning",
    "Reproducibility in ML research",
    "Kernel fusion and memory movement",
    "Batching strategies under load",
    "Fine-tuning versus prompting",
    "Tokenisation and its downstream cost",
    "Serving multi-tenant models",
    "Profiling a training run",
    "Sparse attention implementations",
]

FORMATS = [
    "{topic}",
    "{topic} — a practical walkthrough",
    "Rethinking {lower}",
    "{topic}: what actually matters",
    "A short talk on {lower}",
    "{topic} (updated)",
]


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)


class FixtureProvider:
    name = "fixture"

    def __init__(self, videos_per_page: int = 50, pages: int = 2) -> None:
        self.videos_per_page = videos_per_page
        self.pages = pages

    async def resolve_channel(self, handle: str) -> ExternalChannel | None:
        seed = _seed("channel", handle)
        return ExternalChannel(
            external_id=f"UCfix{seed % 10**16:016d}",
            handle=handle,
            name=handle.lstrip("@").replace("-", " ").title(),
            description="Talks and lectures on machine learning systems.",
            uploads_playlist_id=f"UUfix{seed % 10**16:016d}",
        )

    async def list_uploads(
        self, uploads_playlist_id: str, page_token: str | None
    ) -> Page:
        page_index = int(page_token) if page_token else 0
        now = datetime.now(UTC)
        items: list[ExternalVideo] = []

        for offset in range(self.videos_per_page):
            index = page_index * self.videos_per_page + offset
            seed = _seed(uploads_playlist_id, str(index))

            topic = TOPICS[seed % len(TOPICS)]
            template = FORMATS[(seed >> 8) % len(FORMATS)]
            title = template.format(topic=topic, lower=topic[0].lower() + topic[1:])

            items.append(
                ExternalVideo(
                    external_id=f"fx_{uploads_playlist_id[-8:]}_{index:04d}",
                    title=title,
                    description=(
                        "Conference recording. Metadata only — this talk is not "
                        "indexed for search inside."
                    ),
                    published_at=now - timedelta(days=(seed % 1400) + index),
                    duration_sec=900 + (seed % 4500),
                )
            )

        next_page = page_index + 1
        return Page(
            items=items,
            next_page_token=str(next_page) if next_page < self.pages else None,
            # Costed exactly like the real thing: one unit per page of 50.
            units_spent=1,
        )
