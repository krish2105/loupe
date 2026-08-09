from app.moments import best_sentence, locate, moment_for, split_sentences

"""
Citing a moment rather than a passage.

The behaviour these protect was missing entirely until an evaluation stopped
grading itself: citations returned the start of a three-minute chunk, and the
fixture golden set read its expected timestamps from chunk boundaries, so the
metric confirmed a tautology.
"""


def words_from(text: str, start: float = 0.0, rate: float = 0.5) -> list[dict]:
    """Word timings at a fixed rate, which is enough to test placement."""
    return [
        {"w": word, "s": round(start + index * rate, 2), "e": round(start + (index + 1) * rate, 2)}
        for index, word in enumerate(text.split())
    ]


class TestSplitting:
    def test_splits_on_terminal_punctuation(self):
        assert split_sentences("One thing. Two things! Three?") == [
            "One thing.",
            "Two things!",
            "Three?",
        ]

    def test_does_not_split_on_a_decimal_or_abbreviation(self):
        # No capital follows, so these stay whole.
        assert len(split_sentences("It costs 1.5 gigabytes per sequence.")) == 1

    def test_handles_an_empty_passage(self):
        assert split_sentences("   ") == []


class TestChoosingTheSentence:
    def test_picks_the_sentence_sharing_the_question_s_terms(self):
        sentences = [
            "Generation is sequential and each token needs a forward pass.",
            "The acceptance rate decides whether speculation helps at all.",
            "Measure it at the batch size you actually serve.",
        ]

        assert best_sentence("what decides whether speculation pays off", sentences) == 1

    def test_does_not_let_a_long_sentence_win_on_length_alone(self):
        """
        Normalisation exists for this. The long sentence contains more words
        overall, so an unnormalised count would pick it despite the short one
        being squarely on topic.
        """
        sentences = [
            "Outliers are the reason.",
            (
                "There are many considerations when deploying models including "
                "memory, throughput, latency, scheduling, batching, quantisation "
                "and the many other reasons people care about performance."
            ),
        ]

        assert best_sentence("why does four bit break the model, outliers?", sentences) == 0

    def test_falls_back_to_the_first_sentence_when_nothing_overlaps(self):
        # A safe floor: this is exactly the old behaviour of citing the start.
        sentences = ["Alpha beta gamma.", "Delta epsilon zeta."]

        assert best_sentence("entirely unrelated words here", sentences) == 0

    def test_ignores_stopwords(self):
        sentences = ["The quantisation cliff appears at four bits.", "It is what it is."]

        # "what/is/it" are stopwords; only "quantisation" should count.
        assert best_sentence("what is the quantisation cliff", sentences) == 0

    def test_handles_an_empty_passage(self):
        assert best_sentence("anything", []) == 0


class TestLocating:
    def test_finds_a_phrase_and_returns_its_start(self):
        words = words_from("the cache is what limits how many users you can serve")

        assert locate(words, "what limits how many", 0.0, 100.0) == 1.5

    def test_only_searches_inside_the_window(self):
        """
        Speakers repeat themselves. Without the window every citation of a
        recurring phrase would resolve to its first utterance, which is worse
        than citing the chunk start.
        """
        words = words_from("the key value cache " * 2 + "and then something else")

        early = locate(words, "the key value cache", 0.0, 1.0)
        late = locate(words, "the key value cache", 2.0, 4.0)

        assert early == 0.0
        assert late == 2.0

    def test_returns_none_when_the_phrase_is_absent(self):
        words = words_from("nothing here matches")

        assert locate(words, "a completely different phrase", 0.0, 100.0) is None

    def test_ignores_punctuation_and_case(self):
        words = [
            {"w": "Cache,", "s": 0.0, "e": 0.4},
            {"w": "utilisation", "s": 0.4, "e": 0.9},
            {"w": "matters.", "s": 0.9, "e": 1.4},
        ]

        assert locate(words, "cache utilisation matters", 0.0, 10.0) == 0.0

    def test_returns_none_for_an_empty_phrase(self):
        assert locate(words_from("some words"), "", 0.0, 10.0) is None


class TestTheWholeDecision:
    def test_points_inside_the_chunk_rather_than_at_its_start(self):
        passage = (
            "Prefill comes next and is compute bound. "
            "Then generation begins one token at a time. "
            "Sampling happens on every step and is easy to get wrong."
        )
        words = words_from(passage, start=180.0)

        moment = moment_for(
            "what is easy to get wrong about sampling", passage, words, 180.0, 200.0
        )

        # The sampling sentence starts well after the chunk does.
        assert moment > 185.0

    def test_falls_back_to_the_chunk_start_when_the_phrase_is_not_found(self):
        # Cannot make a citation worse than the behaviour it replaces.
        passage = "A sentence that is not in the word list at all."
        words = words_from("completely different words entirely", start=50.0)

        assert moment_for("anything", passage, words, 50.0, 60.0) == 50.0

    def test_falls_back_when_there_are_no_words(self):
        assert moment_for("q", "Some passage.", [], 12.0, 20.0) == 12.0

    def test_falls_back_on_an_empty_passage(self):
        assert moment_for("q", "", words_from("a b c"), 7.0, 9.0) == 7.0
