from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime

import asyncpg
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .features import VideoFacts, build_profile
from .metrics import summarise
from .personas import PERSONAS, Candidate, generate_history, split_holdout
from .pipeline import (
    Catalogue,
    build_training_rows,
    generate_candidates,
    popularity_baseline,
    rank,
    train,
)

"""
The nightly recommendation job and its offline evaluation.

    uv run python -m app.run            # train, evaluate, report
    uv run python -m app.run --write    # also persist the §6.4 tables

Everything it writes to watch_events carries is_synthetic = true (§12.2).
"""

TOPIC_WORDS = re.compile(r"[a-z][a-z-]{3,}")
STOP = frozenset(
    """with that this from into your their about after before then than very
    just also more most some such only same
    talk talks conference seminar lecture practice updated short rethinking
    what which when where does actually matters""".split()
)

TOP_NEIGHBOURS = 20


def topics_of(title: str, description: str | None) -> frozenset[str]:
    """
    A crude topic vocabulary from the title.

    §6.4's user_topic_affinity needs topics and nothing in the system produces
    them — there is no classifier and no taxonomy. Title keywords are a stand-in
    that is honest about being one: it will conflate "scaling laws" with
    "scaling", and it cannot see that "GPU" and "accelerator" are the same
    subject. Cluster labels over chunk embeddings would be the real answer, and
    would need the corpus Phase 5 does not have.
    """
    text = f"{title} {description or ''}".lower()
    return frozenset(
        word for word in TOPIC_WORDS.findall(text) if word not in STOP
    ) - frozenset({"loupe"})


async def load_catalogue(pool) -> tuple[Catalogue, list[Candidate]]:
    rows = await pool.fetch(
        """
        SELECT v.id, v.title, v.description, v.published_at, v.channel_id,
               c.handle AS channel_handle,
               COALESCE(s.view_count, 0) AS view_count
        FROM videos v
        JOIN channels c ON c.id = v.channel_id
        LEFT JOIN video_stats s ON s.video_id = v.id
        WHERE v.visibility = 'public'
        """
    )

    facts: dict[str, VideoFacts] = {}
    candidates: list[Candidate] = []
    corpus: list[str] = []
    ids: list[str] = []

    for row in rows:
        video_id = str(row["id"])
        facts[video_id] = VideoFacts(
            video_id=video_id,
            channel_id=str(row["channel_id"]),
            published_at=row["published_at"],
            view_count=row["view_count"],
            topics=topics_of(row["title"], row["description"]),
        )
        candidates.append(
            Candidate(
                video_id=video_id,
                channel_handle=row["channel_handle"],
                title=row["title"],
                view_count=row["view_count"],
            )
        )
        corpus.append(f"{row['title']} {row['description'] or ''}")
        ids.append(video_id)

    neighbours = content_neighbours(ids, corpus)
    return Catalogue(facts=facts, neighbours=neighbours), candidates


def content_neighbours(ids: list[str], corpus: list[str]) -> dict[str, list[tuple[str, float]]]:
    """
    §6.4's video_similarity: top-K neighbours per video from content embeddings.

    TF-IDF vectors rather than bge-m3. They are content embeddings and they are
    lexical — "GPU" and "accelerator" are unrelated to them. bge-m3 would be
    better and would take minutes on CPU for three thousand items; this takes a
    second, and the honest note is that the neighbours are lexical.
    """
    if len(ids) < 2:
        return {}

    vectoriser = TfidfVectorizer(max_features=20000, stop_words="english")
    matrix = vectoriser.fit_transform(corpus)

    neighbours: dict[str, list[tuple[str, float]]] = {}
    block = 256

    for start in range(0, len(ids), block):
        similarity = cosine_similarity(matrix[start : start + block], matrix)
        for offset, row in enumerate(similarity):
            index = start + offset
            row[index] = -1.0  # never a neighbour of itself
            top = np.argpartition(row, -TOP_NEIGHBOURS)[-TOP_NEIGHBOURS:]
            ordered = sorted(top, key=lambda j: row[j], reverse=True)
            neighbours[ids[index]] = [
                (ids[j], float(row[j])) for j in ordered if row[j] > 0.05
            ]

    return neighbours


async def ensure_synthetic_users(pool, count: int) -> list[str]:
    """
    One account per persona, created if absent.

    Handles are prefixed so a synthetic account is identifiable by name as well
    as by the is_synthetic column on its events (§12.2).
    """
    ids: list[str] = []
    for index in range(count):
        handle = f"synthetic-{PERSONAS[index].key}"
        existing = await pool.fetchval("SELECT id FROM users WHERE handle = $1", handle)
        if existing:
            ids.append(str(existing))
            continue

        user_id = uuid.uuid4()
        await pool.execute(
            "INSERT INTO users (id, handle, display_name) VALUES ($1, $2, $3)",
            user_id,
            handle,
            f"Synthetic · {PERSONAS[index].key}",
        )
        ids.append(str(user_id))
    return ids


async def main() -> int:
    write = "--write" in sys.argv
    dsn = os.environ.get(
        "DATABASE_URL", "postgres://localhost:5432/loupe_dev"
    ).replace("postgres://", "postgresql://", 1)

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    now = datetime.now(UTC)

    try:
        catalogue, candidates = await load_catalogue(pool)
        if len(candidates) < 50:
            print("Catalogue too small to evaluate.", file=sys.stderr)
            return 1

        user_ids = await ensure_synthetic_users(pool, len(PERSONAS))

        histories: dict[str, list[tuple[VideoFacts, float]]] = {}
        held_out: dict[str, set[str]] = {}
        profiles = {}

        for persona, user_id in zip(PERSONAS, user_ids, strict=True):
            events = generate_history(persona, candidates, user_id, now)
            train_events, holdout = split_holdout(events)

            histories[user_id] = [
                (catalogue.facts[event["video_id"]], event["watch_pct"])
                for event in train_events
                if event["video_id"] in catalogue.facts
            ]
            held_out[user_id] = {v for v in holdout if v in catalogue.facts}
            profiles[user_id] = build_profile(user_id, histories[user_id])

            if write:
                await pool.executemany(
                    """
                    INSERT INTO watch_events
                        (user_id, video_id, position_sec, watch_pct, completed,
                         occurred_at, is_synthetic)
                    VALUES ($1, $2, $3, $4, $5, $6, true)
                    """,
                    [
                        (
                            uuid.UUID(user_id),
                            uuid.UUID(e["video_id"]),
                            int(e["watch_pct"] * 1800),
                            e["watch_pct"],
                            e["completed"],
                            e["occurred_at"],
                        )
                        for e in events
                    ],
                )

        features, labels = build_training_rows(profiles, histories, catalogue, now=now)
        model = train(features, labels)

        model_ranked: dict[str, list[str]] = {}
        baseline_ranked: dict[str, list[str]] = {}

        candidate_recall: dict[str, float] = {}
        no_diversity: dict[str, list[str]] = {}

        for user_id, profile in profiles.items():
            candidate_ids = generate_candidates(profile, catalogue)

            # The ceiling on stage two. Anything stage one misses is
            # unrecoverable, so a low ranker score means nothing until this is
            # known — it is the first thing to look at, not the last.
            relevant = held_out[user_id]
            candidate_recall[user_id] = (
                len(set(candidate_ids) & relevant) / len(relevant) if relevant else 0.0
            )

            model_ranked[user_id] = rank(model, profile, candidate_ids, catalogue, now=now)
            no_diversity[user_id] = rank(
                model, profile, candidate_ids, catalogue, now=now, diversity=False
            )
            baseline_ranked[user_id] = popularity_baseline(profile, catalogue)

        # Does the model personalise at all? Recall can be zero while the
        # ranking is still correct in character — with 3,000 items and ~8
        # held-out draws from a stochastic generator, hitting the specific
        # items is close to impossible, but preferring the right *channels* is
        # not. This separates "the model is wrong" from "the metric cannot see
        # it".
        channel_precision = {}
        for user_id, profile in profiles.items():
            favoured = {c for c, w in profile.channel_weights.items() if w >= 0.1}
            if not favoured:
                continue
            top = model_ranked[user_id][:20]
            base = baseline_ranked[user_id][:20]
            channel_precision[user_id] = {
                "model": sum(
                    1 for v in top if catalogue.facts[v].channel_id in favoured
                ) / max(1, len(top)),
                "baseline": sum(
                    1 for v in base if catalogue.facts[v].channel_id in favoured
                ) / max(1, len(base)),
            }

        model_scores = summarise(model_ranked, held_out, k=20)
        ablation_scores = summarise(no_diversity, held_out, k=20)
        baseline_scores = summarise(baseline_ranked, held_out, k=20)

        if write:
            await persist(pool, profiles, model_ranked, catalogue)

        report = {
            "corpus": "synthetic",
            "users": int(model_scores["users"]),
            "catalogue_size": len(catalogue.facts),
            "training_rows": int(features.shape[0]),
            "candidate_recall": round(
                float(np.mean(list(candidate_recall.values()))), 4
            ),
            "mean_candidates": int(
                np.mean([len(generate_candidates(p, catalogue)) for p in profiles.values()])
            ),
            "model": {
                "recall@20": round(model_scores["recall@20"], 4),
                "ndcg@20": round(model_scores["ndcg@20"], 4),
            },
            "model_without_diversity": {
                "recall@20": round(ablation_scores["recall@20"], 4),
                "ndcg@20": round(ablation_scores["ndcg@20"], 4),
            },
            "popularity_baseline": {
                "recall@20": round(baseline_scores["recall@20"], 4),
                "ndcg@20": round(baseline_scores["ndcg@20"], 4),
            },
            "top20_from_preferred_channels": {
                "model": round(
                    float(np.mean([v["model"] for v in channel_precision.values()])), 4
                ),
                "baseline": round(
                    float(np.mean([v["baseline"] for v in channel_precision.values()])), 4
                ),
            },
            "beats_baseline": bool(
                model_scores["recall@20"] > baseline_scores["recall@20"]
                and model_scores["ndcg@20"] > baseline_scores["ndcg@20"]
            ),
        }
        print(json.dumps(report, indent=2))

        # Per-user, because an aggregate hides the persona the model does badly
        # on — and the skimmer exists precisely so there is one.
        print("\nPer persona (recall@20, model vs popularity):", file=sys.stderr)
        from .metrics import recall_at_k

        for persona, user_id in zip(PERSONAS, user_ids, strict=True):
            relevant = held_out[user_id]
            m = recall_at_k(model_ranked[user_id], relevant, 20)
            b = recall_at_k(baseline_ranked[user_id], relevant, 20)
            print(
                f"  {persona.key:18s} {m:.3f}  vs  {b:.3f}"
                f"   ({len(relevant)} held out)",
                file=sys.stderr,
            )
    finally:
        await pool.close()

    return 0


async def persist(pool, profiles, model_ranked, catalogue: Catalogue) -> None:
    """Write the §6.4 tables the plan defines and nothing has populated until now."""
    await pool.execute("DELETE FROM feed_candidates")
    await pool.execute("DELETE FROM user_topic_affinity")
    await pool.execute("DELETE FROM video_similarity")

    for user_id, profile in profiles.items():
        top_topics = sorted(
            profile.topic_weights.items(), key=lambda kv: kv[1], reverse=True
        )[:40]
        await pool.executemany(
            """
            INSERT INTO user_topic_affinity (user_id, topic, score)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, topic) DO UPDATE SET score = EXCLUDED.score
            """,
            [(uuid.UUID(user_id), topic, min(1.0, score)) for topic, score in top_topics],
        )

        await pool.executemany(
            """
            INSERT INTO feed_candidates (user_id, video_id, rank, score, reason_code)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, video_id) DO UPDATE
            SET rank = EXCLUDED.rank, score = EXCLUDED.score
            """,
            [
                (uuid.UUID(user_id), uuid.UUID(video_id), index, 1.0 - index / 500, "ranked")
                for index, video_id in enumerate(model_ranked[user_id][:200])
            ],
        )

    rows = []
    for video_id, neighbours in catalogue.neighbours.items():
        for position, (neighbour, score) in enumerate(neighbours[:10]):
            rows.append((uuid.UUID(video_id), uuid.UUID(neighbour), position, score))

    for start in range(0, len(rows), 5000):
        await pool.executemany(
            """
            INSERT INTO video_similarity (video_id, neighbour_id, rank, similarity)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (video_id, neighbour_id) DO NOTHING
            """,
            rows[start : start + 5000],
        )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
