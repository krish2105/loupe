from app.routers.catalogue import LINE_CHAR_CAP, build_lines

"""
Transcript line grouping (ADR 0003).

Pure over word timings, so the off-by-one at a sentence boundary is caught here
rather than by someone noticing the highlight is one line ahead of the audio.
"""


def words(*specs: tuple[str, float, float], speaker: str = "SPEAKER_00"):
    return [
        {"w": word, "s": start, "e": end, "spk": speaker}
        for word, start, end in specs
    ]


class TestGrouping:
    def test_a_line_ends_at_a_sentence(self):
        lines = build_lines(
            words(
                ("Serving", 0.0, 0.4),
                ("is", 0.4, 0.6),
                ("queueing.", 0.6, 1.2),
                ("Throughput", 1.4, 2.0),
                ("lies.", 2.0, 2.4),
            )
        )

        assert [line["text"] for line in lines] == [
            "Serving is queueing.",
            "Throughput lies.",
        ]

    def test_a_line_starts_at_its_first_word(self):
        """
        The whole point. A line whose start is inherited from the chunk it came
        from seeks to the wrong place, and §11.1 says that is the failure that
        discredits the intelligence layer.
        """
        lines = build_lines(
            words(("One.", 0.0, 0.5), ("Two.", 10.0, 10.5), ("Three.", 20.0, 20.5))
        )

        assert [line["start_sec"] for line in lines] == [0.0, 10.0, 20.0]

    def test_speech_that_never_stops_is_still_broken_up(self):
        """
        ASR output frequently has no punctuation at all. Without the cap the
        whole episode is one line, which is the bug this endpoint was rewritten
        to fix.
        """
        long_run = words(*[(f"word{i}", i * 0.5, i * 0.5 + 0.4) for i in range(120)])

        lines = build_lines(long_run)

        assert len(lines) > 1
        assert all(len(line["text"]) <= LINE_CHAR_CAP + 20 for line in lines)

    def test_a_speaker_change_always_breaks_the_line(self):
        """Merging two speakers into one line makes an interview unreadable."""
        segments = [
            *words(("So", 0.0, 0.3), ("the", 0.3, 0.5), ("thing", 0.5, 0.9)),
            *words(("Right", 1.0, 1.4), speaker="SPEAKER_01"),
        ]

        lines = build_lines(segments)

        assert len(lines) == 2
        assert lines[0]["speaker"] == "SPEAKER_00"
        assert lines[1]["speaker"] == "SPEAKER_01"

    def test_lines_are_indexed_in_order(self):
        lines = build_lines(words(("A.", 0.0, 0.2), ("B.", 1.0, 1.2), ("C.", 2.0, 2.2)))

        assert [line["index"] for line in lines] == [0, 1, 2]

    def test_the_last_words_are_not_dropped(self):
        # No terminating punctuation, so the final flush is the only thing that
        # emits them.
        lines = build_lines(words(("trailing", 5.0, 5.4), ("words", 5.4, 5.9)))

        assert lines[-1]["text"] == "trailing words"
        assert lines[-1]["end_sec"] == 5.9


class TestMessyInput:
    def test_empty_segments_produce_no_lines(self):
        assert build_lines([]) == []

    def test_blank_words_are_skipped(self):
        lines = build_lines(
            [
                {"w": "   ", "s": 0.0, "e": 0.1},
                {"w": "Real.", "s": 0.2, "e": 0.6},
            ]
        )

        assert [line["text"] for line in lines] == ["Real."]

    def test_a_missing_timestamp_does_not_crash(self):
        """
        Word timings come from ASR output, which is a third party's JSON. A
        missing field should cost one word's precision, not the endpoint.
        """
        lines = build_lines([{"w": "Word."}])

        assert lines[0]["text"] == "Word."
        assert lines[0]["start_sec"] == 0.0
