from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import (
    FEATURE_NAMES,
    UserProfile,
    VideoFacts,
    apply_diversity,
    build_profile,
    featurise,
)

"""
The two-stage recommender — §12.1.

    Stage 1, candidate generation: union of content-similarity neighbours of
    recently watched videos, new uploads from subscribed channels,
    topic-affinity matches, and a trending pool. Target ~500 candidates.

    Stage 2, ranking: a gradient-boosted model.

The two stages exist because scoring the whole catalogue is neither affordable
nor useful — §5 gives the ranker a sub-100ms budget, and three thousand videos
scored per request does not fit in it. Stage one is cheap and recall-oriented;
stage two is expensive and precision-oriented.
"""

CANDIDATE_TARGET = 500


@dataclass
class Catalogue:
    facts: dict[str, VideoFacts]
    #: Top-K content neighbours per video, precomputed (§6.4 video_similarity).
    neighbours: dict[str, list[tuple[str, float]]]

    @property
    def max_views(self) -> int:
        return max((f.view_count for f in self.facts.values()), default=1)

    def trending(self, limit: int) -> list[str]:
        ranked = sorted(
            self.facts.values(), key=lambda f: f.view_count, reverse=True
        )
        return [f.video_id for f in ranked[:limit]]


def generate_candidates(
    profile: UserProfile,
    catalogue: Catalogue,
    *,
    target: int = CANDIDATE_TARGET,
    recent_history: int = 12,
) -> list[str]:
    """
    Stage one. A union, deliberately over-inclusive.

    Recall matters here and precision does not: anything stage one misses is
    unrecoverable, while anything it wrongly includes is simply ranked low.
    """
    candidates: dict[str, None] = {}

    # 1. Content neighbours of what they watched recently.
    for video_id in profile.history[-recent_history:]:
        for neighbour, _ in catalogue.neighbours.get(video_id, []):
            candidates.setdefault(neighbour, None)

    # 2. More from channels they spend time on.
    favoured = {
        channel
        for channel, weight in profile.channel_weights.items()
        if weight >= 0.05
    }
    for facts in catalogue.facts.values():
        if facts.channel_id in favoured:
            candidates.setdefault(facts.video_id, None)

    # 3. Topic-affinity matches.
    liked_topics = {
        topic for topic, weight in profile.topic_weights.items() if weight >= 0.05
    }
    if liked_topics:
        for facts in catalogue.facts.values():
            if facts.topics & liked_topics:
                candidates.setdefault(facts.video_id, None)

    # 4. A trending pool, which is what carries a cold-start user (§12.2) and
    #    also what stops the feed becoming a closed loop of one interest.
    for video_id in catalogue.trending(target // 4):
        candidates.setdefault(video_id, None)

    return [
        video_id
        for video_id in list(candidates)[:target]
        if video_id in catalogue.facts
    ]


def build_training_rows(
    profiles: dict[str, UserProfile],
    histories: dict[str, list[tuple[VideoFacts, float]]],
    catalogue: Catalogue,
    *,
    negatives_per_positive: int = 4,
    seed: int = 17,
    now: datetime | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Positives are watches with their watch percentage as the label. Negatives
    are sampled unwatched videos labelled zero.

    Sampled rather than exhaustive: with three thousand videos and a few dozen
    watches per user, using every unwatched item would make the training set
    99.9% negative and the model would learn to predict zero.
    """
    rng = random.Random(seed)
    now = now or datetime.now(UTC)
    all_ids = list(catalogue.facts)

    rows: list[list[float]] = []
    labels: list[float] = []

    for user_id, profile in profiles.items():
        watched = histories.get(user_id, [])
        if not watched:
            continue

        # The profile must not include the item being predicted, or channel
        # affinity leaks the answer. Rebuilt per positive, leaving that one out.
        for index, (facts, watch_pct) in enumerate(watched):
            others = watched[:index] + watched[index + 1 :]
            leave_one_out = build_profile(user_id, others)

            rows.append(
                featurise(
                    leave_one_out,
                    facts,
                    similarity=_similarity_to_history(facts.video_id, leave_one_out, catalogue),
                    max_views=catalogue.max_views,
                    now=now,
                )
            )
            labels.append(watch_pct)

            for _ in range(negatives_per_positive):
                candidate_id = rng.choice(all_ids)
                if candidate_id in profile.seen:
                    continue
                rows.append(
                    featurise(
                        leave_one_out,
                        catalogue.facts[candidate_id],
                        similarity=_similarity_to_history(
                            candidate_id, leave_one_out, catalogue
                        ),
                        max_views=catalogue.max_views,
                        now=now,
                    )
                )
                labels.append(0.0)

    return np.array(rows, dtype=float), np.array(labels, dtype=float)


def _similarity_to_history(
    video_id: str, profile: UserProfile, catalogue: Catalogue
) -> float:
    """
    Best content similarity between this video and anything the user watched.

    Max rather than mean: a video strongly related to one watched item is a good
    recommendation even if it is unrelated to the other forty, and averaging
    would drown that signal in a broad history.
    """
    best = 0.0
    for watched_id in profile.history:
        for neighbour, score in catalogue.neighbours.get(watched_id, []):
            if neighbour == video_id and score > best:
                best = score
    return best


def train(features: np.ndarray, labels: np.ndarray) -> HistGradientBoostingRegressor:
    """
    §12.1 specifies a gradient-boosted model. This is scikit-learn's histogram
    implementation — the same algorithm family, no extra dependency, and fast
    enough that retraining nightly is unremarkable.
    """
    model = HistGradientBoostingRegressor(
        max_depth=4,
        max_iter=200,
        learning_rate=0.08,
        # Small dataset; without this the model memorises individual users.
        min_samples_leaf=20,
        random_state=17,
    )
    model.fit(features, labels)
    return model


def rank(
    model: HistGradientBoostingRegressor,
    profile: UserProfile,
    candidate_ids: list[str],
    catalogue: Catalogue,
    *,
    now: datetime | None = None,
    exclude_seen: bool = True,
    diversity: bool = True,
) -> list[str]:
    """Stage two, plus §12.1's novelty and diversity terms."""
    now = now or datetime.now(UTC)

    # §12.1's novelty penalty, applied as exclusion. Recommending something
    # already watched is not a mild demotion — it is the feed failing at its
    # only job.
    pool = [
        video_id
        for video_id in candidate_ids
        if not (exclude_seen and video_id in profile.seen)
    ]
    if not pool:
        return []

    rows = np.array(
        [
            featurise(
                profile,
                catalogue.facts[video_id],
                similarity=_similarity_to_history(video_id, profile, catalogue),
                max_views=catalogue.max_views,
                now=now,
            )
            for video_id in pool
        ],
        dtype=float,
    )

    scores = model.predict(rows)
    scored = [
        (video_id, float(score), catalogue.facts[video_id])
        for video_id, score in zip(pool, scores, strict=True)
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    if not diversity:
        return [video_id for video_id, _, _ in scored]

    return [video_id for video_id, _ in apply_diversity(scored)]


def popularity_baseline(
    profile: UserProfile, catalogue: Catalogue, *, exclude_seen: bool = True
) -> list[str]:
    """
    §12.3's baseline. Deliberately given the same unfair advantage as the model
    — it also excludes already-seen items — so the comparison measures ranking
    rather than bookkeeping.
    """
    ranked = sorted(catalogue.facts.values(), key=lambda f: f.view_count, reverse=True)
    return [
        f.video_id
        for f in ranked
        if not (exclude_seen and f.video_id in profile.seen)
    ]


__all__ = [
    "CANDIDATE_TARGET",
    "Catalogue",
    "FEATURE_NAMES",
    "build_training_rows",
    "generate_candidates",
    "popularity_baseline",
    "rank",
    "train",
]
