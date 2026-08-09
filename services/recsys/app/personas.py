from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

"""
Synthetic watch histories — §12.2.

    "Generate synthetic watch histories from plausible persona models, clearly
     labelled as synthetic in the README and in a debug panel."
    "Never present synthetic results as real user data. The disclosure is the
     professional signal."

Every event this produces is written with `is_synthetic = true`, so the
distinction is queryable rather than a claim in prose.

**What this data can and cannot support.** A persona picks videos by rules. A
model trained on the result learns those rules. Beating a popularity baseline
therefore demonstrates that the pipeline works end to end — features, training,
ranking, evaluation — and demonstrates nothing whatsoever about whether the
recommendations would suit a person. §12.3's number is a systems check, not a
quality claim, and the report says so.

The personas below are deliberately noisy for that reason. A generator with
clean rules produces a trivially recoverable signal and a meaninglessly high
score; these carry exploration, popularity bias, and recency bias so the
learnable signal is partial. That makes the exercise informative without making
it honest — nothing makes synthetic data honest except saying what it is.
"""


@dataclass(frozen=True)
class Persona:
    key: str
    #: Channel handles this persona gravitates to.
    favourite_channels: tuple[str, ...]
    #: Words that attract them, matched against titles.
    topics: tuple[str, ...]
    #: How often they watch something outside their preferences.
    exploration: float
    #: How strongly they follow view counts rather than their own taste.
    popularity_bias: float
    #: Typical completion. Drives watch_pct, which the ranker predicts.
    engagement: float
    sessions: int


PERSONAS: tuple[Persona, ...] = (
    Persona(
        key="systems-engineer",
        favourite_channels=("mlsys", "stanford-mlsys"),
        topics=("memory", "bandwidth", "serving", "batching", "inference", "cache"),
        exploration=0.15,
        popularity_bias=0.2,
        engagement=0.72,
        sessions=14,
    ),
    Persona(
        key="researcher",
        favourite_channels=("neurips", "icml"),
        topics=("scaling", "attention", "optimiser", "training", "sparse"),
        exploration=0.25,
        popularity_bias=0.1,
        engagement=0.55,
        sessions=12,
    ),
    Persona(
        key="practitioner",
        favourite_channels=("pytorch-conf", "sys-ml-reading"),
        topics=("quantisation", "retrieval", "decoding", "tokenisation", "structured"),
        exploration=0.3,
        popularity_bias=0.35,
        engagement=0.48,
        sessions=16,
    ),
    Persona(
        key="skimmer",
        favourite_channels=(),
        topics=(),
        # Almost pure popularity. Exists so the dataset contains someone the
        # popularity baseline should beat the model on — without them, the
        # comparison is rigged in the model's favour.
        exploration=0.8,
        popularity_bias=0.8,
        engagement=0.22,
        sessions=10,
    ),
    Persona(
        key="deep-diver",
        favourite_channels=("mlsys",),
        topics=("roofline", "kernel", "profiling", "distributed"),
        exploration=0.1,
        popularity_bias=0.05,
        engagement=0.88,
        sessions=9,
    ),
)


@dataclass(frozen=True)
class Candidate:
    video_id: str
    channel_handle: str
    title: str
    view_count: int


def _seeded(*parts: str) -> random.Random:
    digest = hashlib.blake2b("|".join(parts).encode(), digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


def affinity(persona: Persona, candidate: Candidate) -> float:
    """
    How much this persona is drawn to this video, before noise.

    Deliberately simple and deliberately overlapping — channel preference and
    topic preference both contribute, so no single feature reconstructs the
    persona on its own.
    """
    score = 0.0

    if candidate.channel_handle in persona.favourite_channels:
        score += 0.55

    title = candidate.title.lower()
    matches = sum(1 for topic in persona.topics if topic in title)
    score += min(0.4, matches * 0.2)

    return score


def generate_history(
    persona: Persona,
    catalogue: list[Candidate],
    user_id: str,
    now: datetime | None = None,
) -> list[dict]:
    """
    One persona's watch history, deterministic for a given user id.

    Returns dicts rather than writing them, so the shape can be tested without
    a database.
    """
    if not catalogue:
        return []

    rng = _seeded(persona.key, user_id)
    now = now or datetime.now(UTC)

    max_views = max(c.view_count for c in catalogue) or 1
    events: list[dict] = []
    seen: set[str] = set()

    for session in range(persona.sessions):
        # Sessions walk backwards in time, so the holdout split in §12.3 has a
        # meaningful notion of "the final 20%".
        session_time = now - timedelta(days=(persona.sessions - session) * 2.5)
        watches = rng.randint(2, 5)

        for _ in range(watches):
            if rng.random() < persona.exploration:
                pick = rng.choice(catalogue)
            else:
                # Weighted draw over affinity plus popularity, rather than
                # always taking the argmax — a persona that watches exactly
                # their top item every time is not a person.
                weights = [
                    0.05
                    + affinity(persona, c)
                    + persona.popularity_bias * (c.view_count / max_views)
                    for c in catalogue
                ]
                pick = rng.choices(catalogue, weights=weights, k=1)[0]

            if pick.video_id in seen and rng.random() < 0.85:
                continue
            seen.add(pick.video_id)

            base = persona.engagement + affinity(persona, pick) * 0.25
            watch_pct = max(0.02, min(1.0, rng.gauss(base, 0.18)))

            events.append(
                {
                    "user_id": user_id,
                    "video_id": pick.video_id,
                    "watch_pct": round(watch_pct, 4),
                    "completed": watch_pct >= 0.95,
                    "occurred_at": session_time
                    + timedelta(minutes=rng.randint(0, 90)),
                    "is_synthetic": True,
                }
            )

    events.sort(key=lambda event: event["occurred_at"])
    return events


def split_holdout(
    events: list[dict], holdout_fraction: float = 0.2
) -> tuple[list[dict], set[str]]:
    """
    §12.3: "Hold out the final 20% of each synthetic user's history."

    Split by time, not at random. A random split leaks the future into the
    training set — the model sees what the user watched *after* the items it is
    being asked to predict, which inflates every number and is the single most
    common way an offline recommender result becomes meaningless.
    """
    if not events:
        return [], set()

    ordered = sorted(events, key=lambda event: event["occurred_at"])
    cut = max(1, int(len(ordered) * (1 - holdout_fraction)))

    train = ordered[:cut]
    held = {event["video_id"] for event in ordered[cut:]}

    # An item in both halves is not a prediction target — the model has already
    # seen it, so counting it would reward memorisation.
    trained_on = {event["video_id"] for event in train}
    return train, held - trained_on
