from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

from .ladder import Rung, rungs_for
from .stages import StepFailed

"""
Turning an uploaded file into something playable.

This is the step that had never run. Transcoding was Bunny's job and Bunny was
never provisioned, so `uploaded → transcoding → transcoded` — the first
transition the stage machine documents — had no code behind it, and the entire
catalogue was one fixture stream wearing twenty-two titles.

ffmpeg, invoked as a subprocess. Not a Python binding: the bindings wrap a
particular ffmpeg build and this has to run unchanged on a laptop, on an ARM VM
and in a container, where the only thing reliably present is the binary. The
argument list is also the thing worth reading, and a binding hides it.

The work is deliberately awful to keep in memory: download a file, run a
process per rung, write a playlist, upload a directory. What has a *decision* in
it — which rungs, at what bitrate — lives in ladder.py where it is tested
without ffmpeg, a bucket or a database.
"""

logger = logging.getLogger("pipeline.transcode")

#: Six seconds. Long enough that the request count stays sane over a talk,
#: short enough that seeking lands near where it was asked to.
SEGMENT_SECONDS = 6


async def _run(*args: str) -> str:
    """Run a command, or raise StepFailed carrying enough to diagnose it."""
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        # ffmpeg's diagnosis is in the last few lines; the rest is banner. The
        # whole thing in a log line is unreadable and gets truncated anyway.
        tail = stderr.decode(errors="replace").strip().splitlines()[-4:]
        raise StepFailed(f"{args[0]} exited {process.returncode}: {' / '.join(tail)}")

    return stdout.decode(errors="replace")


async def probe(source: Path) -> tuple[int, float]:
    """
    The source's height and duration.

    Both matter beyond this step. The height decides the ladder; the duration
    is written back to the video row, which is the first time the catalogue has
    a duration that describes the file rather than a fixture's guess.
    """
    raw = await _run(
        "ffprobe", "-v", "error",
        "-show_entries", "stream=height:format=duration",
        "-of", "json", str(source),
    )

    try:
        parsed = json.loads(raw)
        heights = [
            int(stream["height"])
            for stream in parsed.get("streams", [])
            if stream.get("height")
        ]
        duration = float(parsed.get("format", {}).get("duration", 0.0))
    except (ValueError, KeyError, TypeError) as error:
        raise StepFailed(f"could not read the source: {error}") from error

    # An audio-only upload has no video stream and a height of zero. That is a
    # real case — §11 gives audio its own surface — and the ladder handles it.
    return (max(heights) if heights else 0), duration


async def encode_rung(source: Path, out: Path, rung: Rung) -> None:
    out.mkdir(parents=True, exist_ok=True)

    await _run(
        "ffmpeg", "-v", "error", "-y",
        "-i", str(source),
        # -2 keeps the width even, which H.264 requires, and derives it from the
        # source's aspect rather than assuming 16:9. A vertical talk stays
        # vertical; §11's shorts feed depends on that.
        "-vf", f"scale=-2:{rung.height}",
        "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main",
        "-b:v", f"{rung.bitrate}k", "-maxrate", f"{int(rung.bitrate * 1.2)}k",
        "-bufsize", f"{rung.bitrate * 2}k",
        # A keyframe exactly at each segment boundary. Without this ffmpeg cuts
        # where it likes, segments vary wildly in length, and switching
        # rendition mid-playback stutters because the rungs do not line up.
        "-g", str(SEGMENT_SECONDS * 25), "-keyint_min", str(SEGMENT_SECONDS * 25),
        "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-f", "hls",
        "-hls_time", str(SEGMENT_SECONDS),
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", str(out / "seg-%05d.ts"),
        str(out / "index.m3u8"),
    )


async def extract_audio(source: Path, destination: Path) -> None:
    """
    Speech-model audio: 16 kHz, mono, uncompressed.

    Every speech model resamples to 16 kHz internally, so sending anything
    richer uploads bytes that are discarded on arrival. Mono for the same
    reason — a talk is one speaker and a stereo channel doubles the file to
    carry a duplicate.

    The size difference is the point: a 20 MB source becomes a few hundred
    kilobytes per minute, which is what keeps a two-hour talk inside a hosted
    API's upload limit.
    """
    await _run(
        "ffmpeg", "-v", "error", "-y",
        "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(destination),
    )


def master_playlist(rungs: list[Rung], widths: dict[int, int]) -> str:
    """
    The master playlist, best last.

    Order matters more than it looks: hls.js starts on the first variant when
    it has no bandwidth estimate, so listing the largest first means every
    first play begins by fetching the heaviest segments on a connection nobody
    has measured yet.
    """
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

    for rung in rungs:
        width = widths.get(rung.height, 0)
        resolution = f",RESOLUTION={width}x{rung.height}" if width else ""
        # Audio is included in every rung, so the advertised bandwidth has to
        # cover both or the player under-estimates and over-selects.
        bandwidth = (rung.bitrate + 128) * 1000
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth}{resolution}")
        lines.append(f"{rung.name}/index.m3u8")

    return "\n".join(lines) + "\n"


async def transcode_to_hls(source: Path, destination: Path) -> tuple[list[Rung], float]:
    """
    Produce a complete HLS tree under `destination`.

    Rungs run one at a time rather than concurrently. The target is two ARM
    cores, or a laptop someone is also using; three ffmpeg processes competing
    for them finishes no sooner and makes the machine unusable meanwhile.
    """
    height, duration = await probe(source)
    rungs = rungs_for(height)

    widths: dict[int, int] = {}
    for rung in rungs:
        logger.info("encoding %s", rung.name)
        await encode_rung(source, destination / rung.name, rung)

        first = next((destination / rung.name).glob("seg-*.ts"), None)
        if first is not None:
            actual, _ = await probe(first)
            # Read back rather than computed: `scale=-2` rounds to an even
            # width, so the arithmetic answer is sometimes one pixel out, and a
            # master playlist advertising a resolution the segments do not have
            # is the kind of thing that works everywhere except one player.
            widths[rung.height] = round(actual * 16 / 9) if actual else 0

    if not any((destination / rung.name / "index.m3u8").exists() for rung in rungs):
        raise StepFailed("ffmpeg produced no playlists")

    (destination / "master.m3u8").write_text(master_playlist(rungs, widths))
    return rungs, duration


def workspace() -> tempfile.TemporaryDirectory:
    """
    Somewhere to work, cleaned up whatever happens.

    A failed transcode that leaves ten gigabytes behind fills the disk of a
    machine with a 47 GB free-tier volume in a few dozen attempts, and the next
    symptom is unrelated things failing.
    """
    return tempfile.TemporaryDirectory(prefix="loupe-transcode-")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
