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
        assert first_sentences("no full stop here", 3) == "no full stop here"

    def test_empty_text(self):
        assert first_sentences("   ", 2) == ""
