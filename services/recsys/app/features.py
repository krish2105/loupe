from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

"""
Feature extraction — §12.1 stage two.

    "Gradient-boosted model over predicted watch percentage, recency decay,
     channel affinity, topic affinity, a novelty penalty for already-seen
     items, and a diversity term preventing single-topic collapse."

Pure functions over plain data, so the features can be tested without a
database, a model, or a training run. That matters more here than elsewhere: a
feature that is silently always zero does not break anything, it just quietly
removes itself from the model, and the only symptom is a slightly worse number
that looks like the world being hard.
"""

FEATURE_NAMES = (
    "channel_affinity",
    "topic_affinity",
    "content_similarity",
    "popularity",
    "recency",
    "already_seen",
)


@dataclass(frozen=True)
class VideoFacts:
    video_id: str
    channel_id: str
    published_at: datetime | None
    view_count: int
    topics: frozenset[str]


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    #: Fraction of this user's history spent on each channel.
    channel_weights: dict[str, float]
    #: Fraction spent on each topic.
    topic_weights: dict[str, float]
    seen: frozenset[str]
    #: Mean similarity is computed against these; ids they actually watched.
    history: tuple[str, ...]


def recency_score(
    published_at: datetime | None, now: datetime, half_life_days: float = 45.0
) -> float:
    """
    Exponential decay, not a linear one.

    Linear decay makes a two-year-old talk and a four-year-old talk almost
    equally penalised, which is wrong — the interesting distinction is between
    this week and last quarter, and exponential decay puts the resolution there.
    """
    if published_at is None:
        return 0.0

    age_days = max(0.0, (now - published_at).total_seconds() / 86400)
    return math.exp(-age_days / half_life_days)


def popularity_score(view_count: int, max_views: int) -> float:
    """
    Log-scaled.

    Raw view counts are power-law distributed, so a linear feature is dominated
    by the single most-viewed item and every other value collapses toward zero —
    the model would learn "is it the most popular video" rather than "how
    popular is it".
    """
    if max_views <= 0:
        return 0.0
    return math.log1p(view_count) / math.log1p(max_views)


def build_profile(
    user_id: str,
    watched: list[tuple[VideoFacts, float]],
) -> UserProfile:
    """
    A user's tastes, weighted by how much of each video they actually watched.

    Weighting by watch_pct rather than counting views is the point: opening
    something and abandoning it after ten seconds is evidence *against* an
    interest, and counting it equally with a full watch teaches the model the
    opposite of what happened.
    """
    channel_weights: dict[str, float] = {}
    topic_weights: dict[str, float] = {}
    total = 0.0

    for facts, watch_pct in watched:
        weight = max(0.0, watch_pct)
        total += weight
        channel_weights[facts.channel_id] = channel_weights.get(facts.channel_id, 0.0) + weight
        for topic in facts.topics:
            topic_weights[topic] = topic_weights.get(topic, 0.0) + weight

    if total > 0:
        channel_weights = {k: v / total for k, v in channel_weights.items()}
        topic_weights = {k: v / total for k, v in topic_weights.items()}

    return UserProfile(
        user_id=user_id,
        channel_weights=channel_weights,
        topic_weights=topic_weights,
        seen=frozenset(facts.video_id for facts, _ in watched),
        history=tuple(facts.video_id for facts, _ in watched),
    )


def featurise(
    profile: UserProfile,
    candidate: VideoFacts,
    *,
    similarity: float,
    max_views: int,
    now: datetime | None = None,
) -> list[float]:
    now = now or datetime.now(UTC)

    topic_affinity = sum(profile.topic_weights.get(topic, 0.0) for topic in candidate.topics)

    return [
        profile.channel_weights.get(candidate.channel_id, 0.0),
        min(1.0, topic_affinity),
        similarity,
        popularity_score(candidate.view_count, max_views),
        recency_score(candidate.published_at, now),
        1.0 if candidate.video_id in profile.seen else 0.0,
    ]


def apply_diversity(
    ranked: list[tuple[str, float, VideoFacts]],
    penalty: float = 0.18,
) -> list[tuple[str, float]]:
    """
    §12.1's diversity term: prevent single-topic collapse.

    A ranker optimising predicted watch percentage converges on one subject,
    because the user's strongest affinity always scores highest. That produces a
    feed of twenty variations on the same talk, which reads as broken even
    though every item is individually well-predicted.

    Applied after scoring rather than as a feature, because it is a property of
    the *list*, not of any item in it.
    """
    seen_channels: dict[str, int] = {}
    adjusted: list[tuple[str, float]] = []

    for video_id, score, facts in ranked:
        repeats = seen_channels.get(facts.channel_id, 0)
        adjusted.append((video_id, score - repeats * penalty))
        seen_channels[facts.channel_id] = repeats + 1

    adjusted.sort(key=lambda item: item[1], reverse=True)
    return adjusted
