from datetime import UTC, datetime, timedelta

from app.features import (
    UserProfile,
    VideoFacts,
    apply_diversity,
    build_profile,
    featurise,
    popularity_score,
    recency_score,
)
from app.pipeline import Catalogue, generate_candidates, popularity_baseline

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def facts(video_id: str, channel: str, topics: set[str], views: int = 100, age_days: int = 10):
    return VideoFacts(
        video_id=video_id,
        channel_id=channel,
        published_at=NOW - timedelta(days=age_days),
        view_count=views,
        topics=frozenset(topics),
    )


class TestFeatures:
    def test_watch_percentage_weights_the_profile(self):
        """
        Opening something and abandoning it is evidence *against* an interest.
        Counting it equally with a full watch teaches the opposite of what
        happened.
        """
        profile = build_profile(
            "u",
            [
                (facts("a", "ch1", {"memory"}), 0.95),
                (facts("b", "ch2", {"scaling"}), 0.05),
            ],
        )

        assert profile.channel_weights["ch1"] > profile.channel_weights["ch2"]

    def test_recency_decays_exponentially(self):
        fresh = recency_score(NOW - timedelta(days=1), NOW)
        old = recency_score(NOW - timedelta(days=180), NOW)

        assert fresh > old
        assert 0.0 <= old < 0.1

    def test_missing_publication_date_is_not_an_error(self):
        assert recency_score(None, NOW) == 0.0

    def test_popularity_is_log_scaled(self):
        """
        Raw counts are power-law distributed; a linear feature would collapse
        every value toward zero except the single most-viewed item.
        """
        low = popularity_score(100, 1_000_000)
        high = popularity_score(100_000, 1_000_000)

        assert 0.0 < low < high <= 1.0
        # Linear scaling would put low at 0.0001; log keeps it usable.
        assert low > 0.3

    def test_zero_max_views_does_not_divide_by_zero(self):
        assert popularity_score(0, 0) == 0.0

    def test_every_named_feature_is_produced(self):
        profile = build_profile("u", [(facts("a", "ch1", {"memory"}), 0.8)])
        row = featurise(
            profile, facts("b", "ch1", {"memory"}), similarity=0.4, max_views=1000, now=NOW
        )

        # A feature silently missing does not break anything — it just removes
        # itself from the model, and the only symptom is a worse number.
        assert len(row) == 6
        assert all(isinstance(value, float) for value in row)

    def test_seen_items_are_flagged(self):
        profile = build_profile("u", [(facts("a", "ch1", set()), 0.8)])
        row = featurise(
            profile, facts("a", "ch1", set()), similarity=0.0, max_views=1000, now=NOW
        )
        assert row[-1] == 1.0


class TestDiversity:
    def test_it_demotes_repeats_from_one_channel(self):
        """
        §12.1: prevent single-topic collapse. A ranker optimising predicted
        watch percentage converges on one subject, producing twenty variations
        of the same talk.
        """
        ranked = [
            ("a", 0.9, facts("a", "ch1", set())),
            ("b", 0.88, facts("b", "ch1", set())),
            ("c", 0.80, facts("c", "ch2", set())),
        ]

        order = [video_id for video_id, _ in apply_diversity(ranked, penalty=0.2)]

        # The second ch1 item drops below the ch2 item.
        assert order == ["a", "c", "b"]

    def test_a_zero_penalty_preserves_the_original_order(self):
        ranked = [
            ("a", 0.9, facts("a", "ch1", set())),
            ("b", 0.8, facts("b", "ch1", set())),
        ]
        assert [v for v, _ in apply_diversity(ranked, penalty=0.0)] == ["a", "b"]


class TestCandidateGeneration:
    def build(self) -> Catalogue:
        catalogue_facts = {
            f"v{i}": facts(
                f"v{i}",
                f"ch{i % 5}",
                {"memory"} if i % 2 else {"scaling"},
                views=i * 10,
            )
            for i in range(300)
        }
        return Catalogue(facts=catalogue_facts, neighbours={})

    def test_it_returns_at_most_the_target(self):
        catalogue = self.build()
        profile = build_profile("u", [(catalogue.facts["v1"], 0.9)])

        assert len(generate_candidates(profile, catalogue, target=50)) <= 50

    def test_a_cold_start_user_still_gets_candidates(self):
        """
        §12.2 ships a content-only path for new users. An empty profile must
        produce a feed, not an empty page.
        """
        catalogue = self.build()
        empty = UserProfile("u", {}, {}, frozenset(), ())

        candidates = generate_candidates(empty, catalogue)

        # From the trending pool, which is what carries cold start.
        assert len(candidates) > 0

    def test_every_candidate_exists_in_the_catalogue(self):
        catalogue = self.build()
        profile = build_profile("u", [(catalogue.facts["v3"], 0.9)])

        for video_id in generate_candidates(profile, catalogue):
            assert video_id in catalogue.facts


class TestBaseline:
    def test_it_ranks_by_views(self):
        catalogue = Catalogue(
            facts={
                "a": facts("a", "ch1", set(), views=10),
                "b": facts("b", "ch1", set(), views=99),
            },
            neighbours={},
        )
        empty = UserProfile("u", {}, {}, frozenset(), ())

        assert popularity_baseline(empty, catalogue)[0] == "b"

    def test_it_excludes_seen_items_like_the_model_does(self):
        """
        Given the same advantage as the model, so the comparison measures
        ranking rather than bookkeeping.
        """
        catalogue = Catalogue(
            facts={"a": facts("a", "ch1", set(), views=99)}, neighbours={}
        )
        profile = UserProfile("u", {}, {}, frozenset({"a"}), ("a",))

        assert popularity_baseline(profile, catalogue) == []
