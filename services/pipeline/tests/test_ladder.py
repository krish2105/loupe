from app.ladder import LADDER, MAX_HEIGHT, bitrate_for, rungs_for

"""
The rendition ladder.

Pure, and worth testing precisely because the failures are quiet: upscaling
wastes transcoder time and storage without looking wrong, and a source that
falls between rungs silently plays worse than the file that was uploaded.
Neither shows up as an error anywhere.
"""


def heights(source: int) -> list[int]:
    return [rung.height for rung in rungs_for(source)]


class TestNeverUpscaling:
    def test_a_720p_source_gets_the_full_ladder(self):
        assert heights(720) == [360, 540, 720]

    def test_a_1080p_source_is_capped_rather_than_extended(self):
        # Storage, not quality. A 1080p rung roughly doubles what a talk costs
        # to hold, and a catalogue of twenty matters more than a sharper eight.
        assert heights(1080) == [360, 540, 720]
        assert max(heights(1080)) == MAX_HEIGHT

    def test_a_540p_source_stops_at_its_own_height(self):
        assert heights(540) == [360, 540]

    def test_no_rung_ever_exceeds_the_source(self):
        for source in (240, 360, 480, 540, 720, 1080, 2160):
            assert max(heights(source)) <= source, source


class TestOfferingTheSourceHeight:
    def test_a_source_between_rungs_keeps_its_own_quality(self):
        """
        The rule that gets forgotten. A fixed 360/540/720 ladder gives a 480p
        source only its 360p rung, so the talk plays worse than what was
        uploaded and nothing reports a problem.
        """
        assert heights(480) == [360, 480]

    def test_a_source_below_every_rung_still_gets_one(self):
        # An empty ladder would produce a master playlist pointing at nothing.
        assert heights(240) == [240]
        assert heights(144) == [144]

    def test_never_returns_an_empty_ladder(self):
        for source in (1, 100, 240, 361, 719, 4320):
            assert rungs_for(source), source


class TestUnknownSources:
    def test_an_unreadable_height_falls_back_to_the_lowest_rung(self):
        """
        ffprobe failing to report a height is not a reason to lose the talk.
        Encoding at the cap risks upscaling, so the smallest rung is taken and
        the result is small rather than absent.
        """
        assert heights(0) == [LADDER[0]]
        assert heights(-1) == [LADDER[0]]


class TestBitrates:
    def test_lands_on_the_conventional_values(self):
        assert bitrate_for(360) == 700
        assert bitrate_for(540) == 1575
        assert bitrate_for(720) == 2799

    def test_scales_with_area_rather_than_height(self):
        # Doubling the height needs roughly four times the bits, because
        # quality tracks pixel count. A linear table drifts badly at the ends.
        assert round(bitrate_for(720) / bitrate_for(360), 2) == 4.0

    def test_never_drops_below_something_watchable(self):
        # A 16p thumbnail-sized source would otherwise be given ~1 kbps.
        assert bitrate_for(16) >= 120

    def test_rises_with_height(self):
        rungs = rungs_for(1080)
        bitrates = [r.bitrate for r in rungs]
        assert bitrates == sorted(bitrates)


def test_rung_names_match_what_a_playlist_directory_is_called():
    assert [rung.name for rung in rungs_for(720)] == ["360p", "540p", "720p"]
