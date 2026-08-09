from __future__ import annotations

from dataclasses import dataclass

"""
Which renditions to produce, given a source.

Two rules, and the second is the one that gets forgotten.

**Never upscale.** Encoding a 480p talk at 720p produces a bigger file that
looks identical, costs the transcoder time it does not have, and costs storage
we are counting in gigabytes. It is pure loss, and it happens by default in
every ladder written as a fixed list.

**Always offer the source height, capped.** A fixed ladder of 360/540/720 gives
a 480p source only its 360p rung, so a talk plays worse than the file that was
uploaded. Adding the source height as its own rung is what stops that.

The cap is 720p, and it is a storage decision rather than a quality one. Free
tier holds 10 GB; a 1080p rung roughly doubles what a talk costs to store, and
a catalogue of twenty talks matters more here than a sharper one of eight.
"""

#: Ceiling on what is produced, whatever arrives. See above.
MAX_HEIGHT = 720

#: The standard rungs, below the cap. The source height is added separately.
LADDER = (360, 540)


@dataclass(frozen=True)
class Rung:
    height: int
    #: Video bitrate in kbps.
    bitrate: int

    @property
    def name(self) -> str:
        return f"{self.height}p"


def bitrate_for(height: int) -> int:
    """
    A bitrate that scales with pixel count rather than with height.

    Quality tracks area, not vertical resolution, so doubling the height needs
    roughly four times the bits. A linear table drifts badly at the ends — the
    kind of drift that shows up as a 240p rung nobody can read and a 720p one
    twice the size it needs to be.

    Calibrated to land on the conventional values: 360p→700k, 540p→1575k,
    720p→2799k.
    """
    return max(120, round(height * height * 0.0054))


def rungs_for(source_height: int) -> list[Rung]:
    """
    The ladder for one source, best last.

    Always returns at least one rung. A source below every standard rung — a
    phone clip at 240p, a screen capture at 300 — still needs encoding, and
    returning an empty ladder would silently produce a video with no renditions
    and a master playlist pointing at nothing.
    """
    if source_height <= 0:
        # ffprobe could not determine a height. Encoding at the cap is wrong
        # (it may upscale) but refusing outright loses the talk, so take the
        # lowest standard rung and let the result be small rather than absent.
        return [Rung(LADDER[0], bitrate_for(LADDER[0]))]

    top = min(source_height, MAX_HEIGHT)
    heights = sorted({h for h in LADDER if h < source_height} | {top})

    return [Rung(h, bitrate_for(h)) for h in heights]
