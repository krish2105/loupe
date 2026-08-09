from __future__ import annotations

import math

"""
Ranking metrics — §12.3.

    "Report recall@20 and NDCG@20 against a popularity baseline. If the model
     does not beat popularity, say so and analyse why."

Pure functions with their own tests, for the reason Phase 7 established: a
metric's bugs are the only invisible ones. It produces a plausible number
either way, the number goes in a README, and nobody can tell it is wrong by
looking at it.
"""


def recall_at_k(ranked: list[str], relevant: set[str], k: int = 20) -> float:
    """
    What fraction of the held-out items the ranking surfaced in its top k.

    Divided by the number of relevant items rather than by k. A user with three
    held-out videos can score 1.0; a user with fifty cannot be expected to, and
    dividing by k would punish the ranker for the user's watch volume.
    """
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def dcg(gains: list[float]) -> float:
    return sum(gain / math.log2(position + 2) for position, gain in enumerate(gains))


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int = 20) -> float:
    """
    Recall weighted by position — getting the right item at rank 1 beats
    getting it at rank 20.

    Binary relevance: an item was watched or it was not. Graded relevance would
    need a notion of how much a watch is worth, and watch_pct is the generator's
    own output on synthetic data, which would make the metric partly circular.
    """
    if not relevant:
        return 0.0

    gains = [1.0 if item in relevant else 0.0 for item in ranked[:k]]
    ideal = [1.0] * min(len(relevant), k)

    best = dcg(ideal)
    return dcg(gains) / best if best else 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarise(
    per_user: dict[str, list[str]],
    held_out: dict[str, set[str]],
    k: int = 20,
) -> dict[str, float]:
    """
    Averaged over users, not over events.

    Per-event averaging lets one heavy user dominate the score, which is how an
    offline number ends up describing a single person's taste.
    """
    users = [user for user in per_user if held_out.get(user)]

    return {
        "users": float(len(users)),
        f"recall@{k}": mean([recall_at_k(per_user[u], held_out[u], k) for u in users]),
        f"ndcg@{k}": mean([ndcg_at_k(per_user[u], held_out[u], k) for u in users]),
    }
