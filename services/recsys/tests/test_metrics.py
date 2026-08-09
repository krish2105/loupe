import pytest

from app.metrics import dcg, mean, ndcg_at_k, recall_at_k, summarise


class TestRecall:
    def test_everything_found(self):
        assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=20) == 1.0

    def test_nothing_found(self):
        assert recall_at_k(["x", "y"], {"a"}, k=20) == 0.0

    def test_it_divides_by_relevant_not_by_k(self):
        """
        A user with three held-out videos can score 1.0; dividing by k would
        punish the ranker for how much the user happens to watch.
        """
        assert recall_at_k(["a"], {"a"}, k=20) == 1.0

    def test_it_respects_the_cutoff(self):
        ranked = ["x"] * 20 + ["a"]
        assert recall_at_k(ranked, {"a"}, k=20) == 0.0

    def test_no_relevant_items_is_zero(self):
        # An unlabelled user must not silently score 1.0 and inflate the mean.
        assert recall_at_k(["a"], set(), k=20) == 0.0


class TestNdcg:
    def test_position_matters(self):
        early = ndcg_at_k(["a"] + ["x"] * 19, {"a"}, k=20)
        late = ndcg_at_k(["x"] * 19 + ["a"], {"a"}, k=20)

        assert early > late
        assert early == 1.0

    def test_perfect_ranking_scores_one(self):
        assert ndcg_at_k(["a", "b", "c"], {"a", "b", "c"}, k=20) == pytest.approx(1.0)

    def test_it_is_bounded(self):
        score = ndcg_at_k(["a", "x", "b"], {"a", "b"}, k=20)
        assert 0.0 <= score <= 1.0

    def test_nothing_relevant_is_zero(self):
        assert ndcg_at_k(["x", "y"], {"a"}, k=20) == 0.0

    def test_empty_relevant_set_is_zero(self):
        assert ndcg_at_k(["a"], set(), k=20) == 0.0

    def test_dcg_discounts_by_log_position(self):
        # Rank 1 is worth 1/log2(2) = 1; rank 2 is worth 1/log2(3).
        assert dcg([1.0]) == pytest.approx(1.0)
        assert dcg([0.0, 1.0]) == pytest.approx(1 / 1.5849625, rel=1e-4)


class TestSummarise:
    def test_it_averages_over_users_not_events(self):
        """
        Per-event averaging lets one heavy user dominate, which is how an
        offline number ends up describing a single person's taste.
        """
        per_user = {"heavy": ["a"] * 20, "light": ["b"]}
        held = {"heavy": {"z"}, "light": {"b"}}

        result = summarise(per_user, held, k=20)

        # One user scores 0, one scores 1 — the mean is 0.5 regardless of how
        # many events each contributed.
        assert result["recall@20"] == pytest.approx(0.5)
        assert result["users"] == 2.0

    def test_users_with_no_holdout_are_excluded(self):
        per_user = {"a": ["x"], "b": ["y"]}
        held = {"a": {"x"}, "b": set()}

        result = summarise(per_user, held, k=20)

        assert result["users"] == 1.0
        assert result["recall@20"] == 1.0

    def test_empty_input(self):
        assert summarise({}, {}, k=20)["users"] == 0.0


def test_mean_of_nothing_is_zero():
    assert mean([]) == 0.0
