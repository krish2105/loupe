from app.chunk import MAX_TOKENS, MIN_TOKENS, OVERLAP_TOKENS, Word, chunk_words
from app.naming import HeuristicNamer
from app.normalise import display, normalise, normalise_pair


class TestNormalisation:
    """
    §10.2 and §6.5 decision 1: two texts, produced together.

    The normalised one is embedded; the display one is shown. These assert the
    separation holds, because the failure is silent — a product that embeds the
    display text just retrieves slightly worse forever.
    """

    def test_caption_annotations_are_stripped_for_retrieval(self):
        assert normalise("[Music] welcome back [Applause]") == "welcome back"
        assert normalise("(laughs) that is the point") == "that is the point"

    def test_filler_is_stripped_for_retrieval(self):
        assert normalise("um so uh the cache, you know, helps") == "so the cache, helps"

    def test_words_containing_filler_survive(self):
        # The bug this guards: a naive replace turns "umbrella" into "brella".
        assert "umbrella" in normalise("the umbrella term here")
        assert "ahead" in normalise("go ahead")

    def test_speaker_labels_are_stripped(self):
        assert normalise("SPEAKER 1: the point is") == "the point is"

    def test_display_keeps_what_was_actually_said(self):
        source = "[Music] um so the cache, you know, helps"
        assert display(source) == source
        assert normalise(source) != display(source)

    def test_the_pair_comes_from_one_source(self):
        normalised, shown = normalise_pair("  [Music]  um   yes  ")
        assert normalised == "yes"
        assert shown == "[Music] um yes"

    def test_whitespace_is_collapsed_in_both(self):
        assert normalise("a\n\n  b\tc") == "a b c"
        assert display("a\n\n  b\tc") == "a b c"


def words(count: int, *, pause_every: int = 0, start: float = 0.0) -> list[Word]:
    """A word stream at 0.3s per word, optionally with pauses."""
    result = []
    clock = start
    for index in range(count):
        if pause_every and index and index % pause_every == 0:
            clock += 1.0  # longer than PAUSE_SECONDS
        result.append(Word(text=f"w{index}", start=clock, end=clock + 0.25, speaker="A"))
        clock += 0.3
    return result


class TestChunking:
    """
    §10.2: "Split on natural pauses and topic shifts, never fixed windows."

    Fixed windows are the default and they are wrong here — a boundary lands
    mid-sentence almost always, and §11.1 makes citation accuracy the thing the
    whole intelligence layer rests on.
    """

    def test_chunks_stay_inside_the_token_band(self):
        chunks = chunk_words(words(2000, pause_every=120))

        assert chunks
        for chunk in chunks[:-1]:
            assert chunk.token_count <= MAX_TOKENS
        assert any(chunk.token_count >= MIN_TOKENS for chunk in chunks)

    def test_boundaries_land_on_pauses_rather_than_a_fixed_count(self):
        # Pauses every 137 words. A fixed-window chunker would cut at exactly
        # 600 every time; this one should not.
        chunks = chunk_words(words(3000, pause_every=137))
        sizes = {chunk.token_count for chunk in chunks[:-1]}

        assert sizes != {MAX_TOKENS}, "chunker fell back to fixed windows"

    def test_chunks_overlap_so_a_straddling_sentence_is_retrievable(self):
        chunks = chunk_words(words(1500, pause_every=110))

        assert len(chunks) >= 2
        for earlier, later in zip(chunks, chunks[1:], strict=False):
            # The later chunk starts before the earlier one ended.
            assert later.start_sec < earlier.end_sec

    def test_timestamps_are_never_flattened(self):
        source = words(800, pause_every=100)
        chunks = chunk_words(source)

        assert chunks[0].start_sec == source[0].start
        for chunk in chunks:
            assert chunk.end_sec > chunk.start_sec

    def test_every_chunk_carries_a_speaker_when_unambiguous(self):
        chunks = chunk_words(words(700, pause_every=100))
        assert all(chunk.speaker == "A" for chunk in chunks)

    def test_a_chunk_spanning_two_speakers_belongs_to_neither(self):
        stream = words(400) + [
            Word(text=f"x{i}", start=200 + i * 0.3, end=200 + i * 0.3 + 0.25, speaker="B")
            for i in range(400)
        ]
        chunks = chunk_words(stream)
        assert any(chunk.speaker is None for chunk in chunks)

    def test_empty_input_is_not_an_error(self):
        assert chunk_words([]) == []

    def test_it_terminates_on_input_shorter_than_the_overlap(self):
        # The loop-forever case: a final window smaller than OVERLAP_TOKENS.
        assert len(chunk_words(words(OVERLAP_TOKENS - 10))) == 1

    def test_pure_annotation_produces_no_chunk(self):
        silence = [
            Word(text="[Applause]", start=i * 0.3, end=i * 0.3 + 0.2) for i in range(60)
        ]
        # An embedding of an empty string matches everything weakly, which is
        # worse than having no chunk at all.
        assert chunk_words(silence) == []


class TestNaming:
    def test_a_title_uses_terms_that_distinguish_the_span(self):
        corpus = "the model the model serving latency batching cache memory bandwidth"
        span = "memory bandwidth memory bandwidth roofline roofline"

        title = HeuristicNamer().title_for(span, corpus)

        # Not "the model", which dominates the corpus and would title every
        # chapter identically.
        assert "model" not in title.lower()
        assert "roofline" in title.lower() or "bandwidth" in title.lower()

    def test_empty_span_does_not_crash(self):
        assert HeuristicNamer().title_for("", "some corpus") == "Untitled section"
