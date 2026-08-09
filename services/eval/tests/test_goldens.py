import json
from pathlib import Path

import pytest

from app.goldens import CorpusMismatch, GoldenSet, assert_corpus_matches, load

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "goldens"


class TestCorpusBinding:
    """
    The safeguard that stops this repository producing its most damaging
    possible artefact: a benchmark table whose numbers are arithmetically
    correct and mean nothing.

    Every label in a golden set encodes a claim about a specific transcript.
    Score it against different transcripts and nothing looks wrong.
    """

    def test_matching_corpus_is_allowed(self):
        golden = GoldenSet(version="v1", corpus="fixture", note="", cases=[])
        assert_corpus_matches(golden, "fixture")

    def test_mismatched_corpus_is_refused(self):
        golden = GoldenSet(version="v1", corpus="fixture", note="", cases=[])

        with pytest.raises(CorpusMismatch) as raised:
            assert_corpus_matches(golden, "whisperx")

        # The message has to explain why, or someone will "fix" it by editing
        # the corpus field.
        assert "mean nothing" in str(raised.value)

    def test_a_mixed_corpus_is_refused(self):
        golden = GoldenSet(version="v1", corpus="fixture", note="", cases=[])

        with pytest.raises(CorpusMismatch):
            assert_corpus_matches(golden, "mixed:fixture+whisperx")

    def test_an_empty_corpus_is_refused(self):
        golden = GoldenSet(version="v1", corpus="fixture", note="", cases=[])

        with pytest.raises(CorpusMismatch):
            assert_corpus_matches(golden, "empty")


class TestTheShippedGoldenSet:
    def test_it_loads(self):
        golden = load(GOLDEN_DIR / "fixture-v1.json")
        assert golden.corpus == "fixture"
        assert len(golden.cases) > 0

    def test_every_case_has_a_category_the_plan_names(self):
        golden = load(GOLDEN_DIR / "fixture-v1.json")
        # §11.2's five, minus non-English per §17 decision 3.
        allowed = {"factual", "cross_video", "out_of_scope", "adversarial"}

        assert {case.category for case in golden.cases} <= allowed

    def test_refusal_cases_carry_no_expected_timestamp(self):
        """
        A case that should be refused has no correct citation, so a timestamp
        on it would be scored against an answer that should never exist.
        """
        golden = load(GOLDEN_DIR / "fixture-v1.json")

        for case in golden.cases:
            if case.should_refuse:
                assert case.expected_start_sec is None, case.id

    def test_answerable_cases_carry_a_timestamp_to_check(self):
        golden = load(GOLDEN_DIR / "fixture-v1.json")

        for case in golden.cases:
            if not case.should_refuse:
                assert case.expected_start_sec is not None, case.id

    def test_ids_are_unique(self):
        golden = load(GOLDEN_DIR / "fixture-v1.json")
        ids = [case.id for case in golden.cases]
        assert len(ids) == len(set(ids))

    def test_every_case_carries_a_note_explaining_the_label(self):
        """
        §11.2 wants a *hand-labelled* set. A label without a reason cannot be
        reviewed, disputed, or re-derived by anyone else.
        """
        golden = load(GOLDEN_DIR / "fixture-v1.json")
        assert all(case.note.strip() for case in golden.cases)

    def test_the_set_states_what_it_cannot_measure(self):
        payload = json.loads((GOLDEN_DIR / "fixture-v1.json").read_text())
        note = " ".join(payload["note"])

        # The note is part of the artefact, not commentary around it.
        assert "NOT MEANINGFUL" in note
        assert "cross-video" in note.lower()

    def test_there_are_both_refusable_and_answerable_cases(self):
        golden = load(GOLDEN_DIR / "fixture-v1.json")
        refusable = [case for case in golden.cases if case.should_refuse]
        answerable = [case for case in golden.cases if not case.should_refuse]

        # A set of only refusals is passed by a system that refuses everything.
        assert len(refusable) >= 5
        assert len(answerable) >= 5

    def test_adversarial_cases_are_domain_adjacent_refusals(self):
        """
        The adversarial category exists to catch answering from adjacent
        knowledge — questions that sound like this talk but are not in it.
        """
        golden = load(GOLDEN_DIR / "fixture-v1.json")
        adversarial = [c for c in golden.cases if c.category == "adversarial"]

        assert adversarial
        assert all(case.should_refuse for case in adversarial)
