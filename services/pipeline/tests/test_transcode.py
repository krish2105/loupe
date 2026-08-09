import pytest

from app.ladder import Rung, rungs_for
from app.transcode import ffmpeg_available, master_playlist, probe, transcode_to_hls

"""
Transcoding.

The playlist is pure and tested directly. The rest needs ffmpeg, so it is
skipped where ffmpeg is absent rather than mocked — a mocked subprocess would
assert that the arguments are the ones written above, which is the one thing
about this code that cannot be wrong in an interesting way.
"""

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_available(), reason="ffmpeg and ffprobe are not on this machine"
)


class TestMasterPlaylist:
    def test_lists_rungs_worst_first(self):
        """
        hls.js starts on the first variant when it has no bandwidth estimate.
        Listing the largest first means every first play begins by fetching the
        heaviest segments over a connection nobody has measured.
        """
        playlist = master_playlist(rungs_for(720), {360: 640, 540: 960, 720: 1280})
        variants = [line for line in playlist.splitlines() if line.endswith("index.m3u8")]

        assert variants == ["360p/index.m3u8", "540p/index.m3u8", "720p/index.m3u8"]

    def test_advertises_bandwidth_including_audio(self):
        # Audio rides in every rung. Advertising video-only makes the player
        # under-estimate and over-select.
        playlist = master_playlist([Rung(360, 700)], {360: 640})

        assert "BANDWIDTH=828000" in playlist

    def test_omits_a_resolution_it_does_not_know(self):
        # Better than advertising 0x360, which some players read as a hint and
        # others reject outright.
        playlist = master_playlist([Rung(360, 700)], {})

        assert "RESOLUTION" not in playlist

    def test_is_a_valid_playlist(self):
        playlist = master_playlist(rungs_for(540), {360: 640, 540: 960})

        assert playlist.startswith("#EXTM3U\n")
        assert playlist.endswith("\n")


@needs_ffmpeg
@pytest.mark.asyncio
class TestAgainstRealMedia:
    async def _make_source(self, tmp_path, size="1280x720", seconds=4):
        import asyncio

        source = tmp_path / "source.mp4"
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=25:duration={seconds}",
            "-f", "lavfi", "-i", f"sine=duration={seconds}",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
        )
        await process.communicate()
        return source

    async def test_reads_height_and_duration(self, tmp_path):
        source = await self._make_source(tmp_path)
        height, duration = await probe(source)

        assert height == 720
        assert 3.5 < duration < 4.5

    async def test_produces_a_playable_tree(self, tmp_path):
        source = await self._make_source(tmp_path)
        out = tmp_path / "hls"
        out.mkdir()

        rungs, duration = await transcode_to_hls(source, out)

        assert [r.name for r in rungs] == ["360p", "540p", "720p"]
        assert (out / "master.m3u8").exists()
        for rung in rungs:
            assert (out / rung.name / "index.m3u8").exists()
            assert list((out / rung.name).glob("seg-*.ts")), rung.name

    async def test_never_upscales_a_small_source(self, tmp_path):
        """
        The rule that costs real money when it is missed. A 480p source encoded
        at 720p is a bigger file that looks identical.
        """
        source = await self._make_source(tmp_path, size="854x480")
        out = tmp_path / "hls"
        out.mkdir()

        rungs, _ = await transcode_to_hls(source, out)

        assert [r.name for r in rungs] == ["360p", "480p"]

    async def test_keeps_a_vertical_source_vertical(self, tmp_path):
        """
        `scale=-2:height` derives width from the source's aspect. Assuming 16:9
        would letterbox every short, and §11's shorts feed is vertical.
        """
        source = await self._make_source(tmp_path, size="720x1280")
        out = tmp_path / "hls"
        out.mkdir()

        rungs, _ = await transcode_to_hls(source, out)
        segment = next((out / rungs[0].name).glob("seg-*.ts"))
        height, _ = await probe(segment)

        assert height == rungs[0].height
