from app.summarise import KEY_POINTS, first_sentences, summarise


def spread_corpus(count: int = 25):
    """A talk with a clear early topic and a clear late one."""
    texts = []
    embeddings = []
    starts = []
    for index in range(count):
        early = index < count // 2
        texts.append(
            f"Passage {index}. "
            + ("Memory bandwidth bounds this." if early else "Batching changes latency.")
        )
        # Two clusters, so the centroid is meaningful.
        embeddings.append([1.0, 0.0] if early else [0.0, 1.0])
        starts.append(float(index * 120))
    return texts, starts, embeddings


class TestSummaryContract:
    """§11: TL;DR of at most three sentences, plus five key points with start_sec."""

    def test_key_points_carry_a_timestamp(self):
        texts, starts, embeddings = spread_corpus()
        result = summarise(texts, starts, embeddings)

        assert result is not None
        # The timestamp is the reason each point was selected from a chunk
        # rather than written freely — a summary you can jump into.
        assert all(point.start_sec in starts for point in result.key_points)

    def test_it_produces_at_most_five_key_points(self):
        texts, starts, embeddings = spread_corpus(40)
        result = summarise(texts, starts, embeddings)

        assert result is not None
        assert len(result.key_points) <= KEY_POINTS

    def test_key_points_are_spread_across_the_talk(self):
        """
        Without the spread constraint every key point comes from wherever the
        speaker was most on-topic — usually the opening — and the summary
        silently describes only the first ten minutes.
        """
        texts, starts, embeddings = spread_corpus(40)
        result = summarise(texts, starts, embeddings)

        assert result is not None
        latest = max(point.start_sec for point in result.key_points)
        assert latest > starts[len(starts) // 2]

    def test_the_tldr_is_at_most_three_sentences(self):
        texts, starts, embeddings = spread_corpus()
        result = summarise(texts, starts, embeddings)

        assert result is not None
        assert result.tldr.count(".") <= 3

    def test_key_points_are_in_order(self):
        texts, starts, embeddings = spread_corpus(30)
        result = summarise(texts, starts, embeddings)

        assert result is not None
        times = [point.start_sec for point in result.key_points]
        assert times == sorted(times)


class TestFailureMode:
    """§11: "Hide the block. Never show a partial summary." """

    def test_too_little_content_produces_nothing(self):
        assert summarise(["one"], [0.0], [[1.0, 0.0]]) is None

    def test_mismatched_inputs_produce_nothing_rather_than_crashing(self):
        assert summarise(["a", "b", "c", "d", "e"], [0.0] * 5, [[1.0]]) is None

    def test_empty_input_produces_nothing(self):
        assert summarise([], [], []) is None


class TestSentenceSplitting:
    def test_it_takes_whole_sentences(self):
        assert first_sentences("One. Two. Three. Four.", 2) == "One. Two."

    def test_it_copes_with_no_terminator(self):
        # Capitalised, because a chunk with no terminator is usually one that
        # got cut mid-sentence, and this text becomes page copy.
        assert first_sentences("no full stop here", 3) == "No full stop here"

    def test_empty_text(self):
        assert first_sentences("   ", 2) == ""


class TestSentenceSelection:
    def test_a_restated_sentence_is_not_counted_twice(self):
        """
        Found by reading the video page, not by a test. A chunk spanning a
        speaker's restatement produced a three-sentence TL;DR carrying one
        sentence of information.
        """
        text = (
            "We store the keys across decoding steps. "
            "Paged attention removes the contiguous allocation requirement. "
            "We store the keys across decoding steps. "
            "Arithmetic intensity is what actually bounds you."
        )

        assert first_sentences(text, 3) == (
            "We store the keys across decoding steps. "
            "Paged attention removes the contiguous allocation requirement. "
            "Arithmetic intensity is what actually bounds you."
        )

    def test_repeats_are_matched_regardless_of_case_and_spacing(self):
        text = "The cache is the point.  the  cache is the point. Something else."

        assert first_sentences(text, 3) == "The cache is the point. Something else."

    def test_a_passage_starting_mid_sentence_still_reads_like_one(self):
        """
        Chunks split on pauses and overlap, so a passage often starts partway
        through a sentence. Correct for retrieval, broken as page copy.
        """
        assert first_sentences("changes the memory arithmetic again.", 1) == (
            "Changes the memory arithmetic again."
        )

    def test_it_still_stops_at_the_requested_count(self):
        text = "One. Two. Three. Four."

        assert first_sentences(text, 2) == "One. Two."

    def test_empty_text_produces_nothing_rather_than_an_index_error(self):
        assert first_sentences("   ", 3) == ""


class TestKeyPointDeduplication:
    def test_a_point_the_speaker_returns_to_appears_once(self):
        """
        The spread rule takes one passage per fifth of the talk. When a speaker
        comes back to a point, two fifths can land on the same sentence, and a
        five-point summary carrying the same line twice is worse than a
        four-point one that does not.
        """
        repeated = "Arithmetic intensity is what actually bounds you."
        texts = [
            "Opening remarks about the agenda.",
            "The roofline model has two regimes.",
            repeated,
            "Batching changes tail latency.",
            repeated,
            "Closing thoughts on deployment.",
        ]
        starts = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0]
        embeddings = [[1.0, 0.0] for _ in texts]

        summary = summarise(texts, starts, embeddings)

        assert summary is not None
        assert len(summary.key_points) == len({p.text for p in summary.key_points})
        assert sum(1 for p in summary.key_points if p.text == repeated) <= 1

    def test_a_talk_that_says_one_thing_produces_no_summary(self):
        """
        §11: hide the block rather than show a partial summary. If deduplication
        leaves a single point, there was nothing to summarise.
        """
        texts = ["The same sentence."] * 6
        starts = [float(i * 100) for i in range(6)]
        embeddings = [[1.0, 0.0] for _ in texts]

        assert summarise(texts, starts, embeddings) is None
