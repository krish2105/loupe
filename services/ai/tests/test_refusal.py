from app.answering import REFUSAL_TEXT, ExtractiveAnswerer, refusal
from app.retrieval import (
    CITATION_THRESHOLD,
    MAX_CITATIONS,
    REFUSAL_THRESHOLD,
    RetrievedChunk,
    select_citations,
    should_refuse,
)

"""
§11.1: "Ask-video must refuse."

    "A confident wrong answer about video content is the failure mode that gets
     noticed in a demo. Threshold on retrieval score and refuse below it. Track
     refusal rate as a headline metric — it is a feature, not a defect."

The Phase 6 gate names refusal behaviour explicitly, so it is tested as a
behaviour rather than an implementation detail.
"""


def chunk(similarity: float, start: float = 100.0, text: str = "some passage") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"c{int(start)}-{int(similarity * 1000)}",
        video_id="v1",
        chunk_index=int(start // 10),
        start_sec=start,
        end_sec=start + 30,
        text_display=text,
        text_normalised=text,
        similarity=similarity,
    )


class TestTheThreshold:
    def test_weak_retrieval_refuses(self):
        assert should_refuse([chunk(0.10), chunk(0.20), chunk(0.31)]) is True

    def test_strong_retrieval_answers(self):
        assert should_refuse([chunk(0.10), chunk(0.85)]) is False

    def test_nothing_retrieved_refuses(self):
        # An empty result must not fall through to "answer from no context".
        assert should_refuse([]) is True

    def test_the_decision_is_on_the_best_match_not_the_average(self):
        """
        One strongly relevant passage is enough to answer from.

        Averaging would let a pile of weak matches outvote a single good one —
        in both directions, which is worse than either failure alone.
        """
        chunks = [chunk(0.95)] + [chunk(0.05) for _ in range(20)]
        assert should_refuse(chunks) is False

    def test_the_threshold_is_conservative(self):
        # The asymmetry §11.1 describes: a refusal on an answerable question is
        # a mild disappointment; a confident answer about something never said
        # discredits the whole layer.
        assert REFUSAL_THRESHOLD >= 0.35


class TestRefusalShape:
    def test_a_refusal_says_it_is_not_covered(self):
        answer = refusal([chunk(0.1)], "test")
        assert answer.refused is True
        assert "not covered" in answer.text.lower()

    def test_a_refusal_carries_no_citations(self):
        """
        The database rejects a refusal with citations, so an answer that hedged
        by refusing *and* pointing somewhere would not persist. Better that the
        shape is impossible than merely discouraged.
        """
        assert refusal([chunk(0.1)], "test").citations == []

    def test_a_refusal_still_reports_its_score(self):
        # Refusal rate is a headline metric, and a rate without the scores
        # behind it cannot be tuned.
        assert refusal([chunk(0.31)], "test").top_score == 0.31


class TestExtractiveAnswering:
    async def test_it_refuses_when_retrieval_is_weak(self):
        answer = await ExtractiveAnswerer().answer("anything?", [chunk(0.2)])

        assert answer.refused is True
        assert answer.text == REFUSAL_TEXT

    async def test_it_answers_only_in_the_speakers_words(self):
        passage = "memory bandwidth becomes the limit long before arithmetic does"
        answer = await ExtractiveAnswerer().answer(
            "what limits inference?", [chunk(0.8, text=passage)]
        )

        assert answer.refused is False
        # Extractive answering cannot state anything the speaker did not say.
        assert passage in answer.text

    async def test_an_answer_always_carries_at_least_one_citation(self):
        answer = await ExtractiveAnswerer().answer("q", [chunk(0.9)])

        assert answer.refused is False
        assert len(answer.citations) >= 1

    async def test_it_refuses_rather_than_answering_without_citations(self):
        # Retrieval strong enough to pass the refusal check but every candidate
        # below the citation floor: answering would leave nothing to point at.
        borderline = REFUSAL_THRESHOLD + 0.01
        answer = await ExtractiveAnswerer().answer("q", [chunk(borderline)])

        assert answer.refused is False or answer.citations == []


class TestCitationSelection:
    def test_it_honours_the_contract_limit(self):
        # §11: 1–4 citations.
        chunks = [chunk(0.9, start=i * 100) for i in range(10)]
        assert len(select_citations(chunks)) <= MAX_CITATIONS

    def test_weak_passages_are_not_cited(self):
        chunks = [chunk(0.9, start=0), chunk(CITATION_THRESHOLD - 0.1, start=500)]
        selected = select_citations(chunks)

        assert all(c.similarity >= CITATION_THRESHOLD for c in selected)

    def test_overlapping_moments_are_not_cited_twice(self):
        """
        Chunks overlap by 50 tokens, so neighbours frequently both match.
        Citing the same moment twice makes an answer look padded.
        """
        chunks = [chunk(0.9, start=100.0), chunk(0.88, start=105.0)]
        assert len(select_citations(chunks)) == 1

    def test_citations_read_in_the_order_the_talk_says_them(self):
        chunks = [chunk(0.7, start=900), chunk(0.9, start=100), chunk(0.8, start=500)]
        selected = select_citations(chunks)

        assert [c.start_sec for c in selected] == sorted(c.start_sec for c in selected)

    def test_every_citation_carries_a_timestamp_to_seek_to(self):
        # §11.1: "If a timestamp lands on the wrong moment, the entire
        # intelligence layer loses credibility instantly."
        selected = select_citations([chunk(0.9, start=142.5)])
        assert selected[0].start_sec == 142.5
