import pytest

from app.metrics import (
    TIMESTAMP_TOLERANCE_SEC,
    best_timestamp_hit,
    faithfulness,
    precision_at_k,
    recall_at_k,
    tally_refusals,
    timestamp_hit,
)

"""
Metric implementations, tested against cases where the right answer is known
by hand.

A metric's bugs are the only ones that are invisible: it produces a plausible
number either way, the number goes in a README, and no one can tell it is wrong
by looking at it. A broken retrieval system gets noticed; a broken precision@5
gets published.
"""


class TestPrecisionAtK:
    def test_all_relevant(self):
        assert precision_at_k(["a", "b", "c", "d", "e"], {"a", "b", "c", "d", "e"}) == 1.0

    def test_none_relevant(self):
        assert precision_at_k(["x", "y"], {"a"}) == 0.0

    def test_it_divides_by_k_not_by_what_was_returned(self):
        """
        A system returning two results and getting both right must not score
        the same as one returning five and getting five right. Otherwise the
        winning strategy is to return one confident result.
        """
        assert precision_at_k(["a", "b"], {"a", "b"}, k=5) == pytest.approx(0.4)

    def test_it_only_looks_at_the_top_k(self):
        # The relevant item is sixth, so precision@5 is zero.
        assert precision_at_k(["x"] * 5 + ["a"], {"a"}, k=5) == 0.0

    def test_empty_retrieval(self):
        assert precision_at_k([], {"a"}) == 0.0

    def test_k_of_zero_is_not_a_division_by_zero(self):
        assert precision_at_k(["a"], {"a"}, k=0) == 0.0


class TestRecallAtK:
    def test_finds_half(self):
        assert recall_at_k(["a"], {"a", "b"}, k=5) == 0.5

    def test_no_relevant_items_is_zero_not_one(self):
        # An empty relevant set means the case is unlabelled; scoring it 1.0
        # would silently inflate the average.
        assert recall_at_k(["a"], set()) == 0.0


class TestTimestampAccuracy:
    """§11.2: correct within ±5 seconds."""

    def test_exact(self):
        assert timestamp_hit(100.0, 100.0) is True

    def test_inside_the_band(self):
        assert timestamp_hit(104.9, 100.0) is True
        assert timestamp_hit(95.1, 100.0) is True

    def test_on_the_boundary_counts(self):
        assert timestamp_hit(105.0, 100.0) is True

    def test_outside_the_band(self):
        assert timestamp_hit(106.0, 100.0) is False

    def test_a_missing_citation_is_not_a_hit(self):
        # Rather than being skipped, which would let a system that cites
        # nothing score perfectly on the citations it did not make.
        assert timestamp_hit(None, 100.0) is False

    def test_any_of_the_citations_may_be_the_right_one(self):
        """
        An answer carries 1–4 citations and the reader clicks the right one.
        Requiring the *first* to be correct measures ranking, which is a
        different claim than citation accuracy.
        """
        assert best_timestamp_hit([500.0, 102.0, 900.0], 100.0) is True

    def test_none_of_the_citations_landing_is_a_miss(self):
        assert best_timestamp_hit([500.0, 900.0], 100.0) is False

    def test_no_citations_at_all_is_a_miss(self):
        assert best_timestamp_hit([], 100.0) is False

    def test_the_tolerance_is_the_documented_one(self):
        assert TIMESTAMP_TOLERANCE_SEC == 5.0


class TestRefusalAccounting:
    def test_a_perfect_system(self):
        counts = tally_refusals([(True, True), (False, False), (True, True)])

        assert counts.accuracy == 1.0
        assert counts.false_answer_rate == 0.0

    def test_the_dangerous_failure_is_counted_separately(self):
        """
        §11.1: answering something that should have been refused is the failure
        that discredits the layer. Accuracy hides it — a system that answers
        everything scores well on a mostly-answerable set while doing exactly
        the wrong thing.
        """
        counts = tally_refusals([(True, False)] + [(False, False)] * 9)

        assert counts.accuracy == pytest.approx(0.9)
        assert counts.false_answer_rate == 1.0  # every refusable case was answered

    def test_over_refusing_is_visible_too(self):
        counts = tally_refusals([(False, True)] * 4 + [(True, True)])

        assert counts.false_refusals == 4
        assert counts.refusal_rate == 1.0

    def test_refusal_rate_is_reported_as_a_rate_not_a_verdict(self):
        counts = tally_refusals([(True, True), (False, False)])
        assert counts.refusal_rate == 0.5

    def test_an_empty_set_does_not_divide_by_zero(self):
        counts = tally_refusals([])
        assert counts.accuracy == 0.0
        assert counts.false_answer_rate == 0.0
        assert counts.refusal_rate == 0.0


class TestFaithfulness:
    def test_an_extractive_answer_is_fully_supported(self):
        source = "memory bandwidth becomes the limit long before arithmetic does"
        # Extractive answering quotes its sources, so this is 1.0 by
        # construction — any drop means it started paraphrasing.
        assert faithfulness(source, [source]) == pytest.approx(1.0)

    def test_an_invented_claim_scores_low(self):
        source = "memory bandwidth becomes the limit"
        answer = "The speaker recommends buying more expensive accelerators immediately."

        assert faithfulness(answer, [source]) < 0.3

    def test_it_is_measured_per_sentence(self):
        source = "memory bandwidth becomes the limit"
        # One supported sentence, one invented.
        answer = "Memory bandwidth becomes the limit. Quantum computing solves this."

        score = faithfulness(answer, [source])
        assert 0.3 < score < 0.9

    def test_no_sources_means_unsupported(self):
        assert faithfulness("anything at all", []) == 0.0

    def test_an_empty_answer_is_unsupported(self):
        assert faithfulness("   ", ["a source"]) == 0.0
