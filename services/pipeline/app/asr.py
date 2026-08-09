from __future__ import annotations

import hashlib
from typing import Protocol

from .chunk import Word

"""
Speech recognition — §10.2.

    "Word-level timestamped segments. Word timing is a hard requirement —
     citation accuracy depends on it."

§5.2 rejects plain Whisper for exactly this: it does not give clean word
timing, and §11.1 makes the credibility of the whole intelligence layer rest on
a citation landing on the right moment. So the interface returns words, not
segments, and nothing downstream can lose the timing because there is no
coarser representation to fall back to.

The fixture transcriber exists because the owned catalogue currently points at
a test stream with no speech in it. It produces a deterministic, topically
segmented transcript so the chunker, the drift detector, and the chapter
namer can be exercised end to end. Its output is stored with
`engine = 'fixture'`, so every row it produced is identifiable with one query
and can be deleted the moment real audio exists.
"""


class Transcriber(Protocol):
    engine: str
    engine_version: str

    def transcribe(self, audio_ref: str, duration_sec: int) -> list[Word]: ...


# Distinct topics so drift detection has genuine boundaries to find rather
# than uniform noise. Each is a plausible section of a systems talk.
_SECTIONS: list[tuple[str, list[str]]] = [
    (
        "intro",
        """thanks for having me today i want to talk about what happens when you
        actually try to serve one of these models under real traffic rather than
        in a benchmark the short version is that most of what you read about
        does not survive contact with production""".split(),
    ),
    (
        "attention",
        """so attention costs scale with the square of the sequence length that
        is the part everyone knows what matters more is where that quadratic
        term stops being the thing that hurts you in practice it is usually not
        where people expect and the crossover point moves with your batch
        size""".split(),
    ),
    (
        "memory",
        """memory bandwidth becomes the limit long before arithmetic does you
        can see this on a roofline plot the kernel is bandwidth bound almost
        everywhere which is why a faster accelerator often does not make
        inference faster at all""".split(),
    ),
    (
        "caching",
        """this is where key value caching earns its keep we store the keys and
        the values across decoding steps so the model does not recompute them
        paged attention changes the memory arithmetic again by removing the
        contiguous allocation requirement""".split(),
    ),
    (
        "batching",
        """continuous batching is the other half of the story you admit requests
        into the running batch as slots free up rather than waiting for the whole
        batch to finish tail latency behaves very differently once you do
        that""".split(),
    ),
    (
        "questions",
        """i think that is everything i wanted to cover happy to take questions
        now yes go ahead at the back that is a good question about quantisation
        and where the accuracy actually degrades""".split(),
    ),
]


class FixtureTranscriber:
    """Deterministic word-level transcript. Never presented as real speech."""

    engine = "fixture"
    engine_version = "1"

    def transcribe(self, audio_ref: str, duration_sec: int) -> list[Word]:
        seed = int(hashlib.blake2b(audio_ref.encode(), digest_size=4).hexdigest(), 16)

        target_words = max(1200, int(duration_sec * 2.4))
        per_word = max(0.18, duration_sec / max(1, target_words))

        # Each section is emitted as one long contiguous span rather than
        # cycling short ones.
        #
        # The first version cycled six ~40-word sections, and chapter detection
        # found nothing on any talk — correctly. Chunks are 300-600 tokens, so
        # every chunk contained all six topics in equal measure and there was
        # no drift between neighbours to detect. A fixture whose topics are an
        # order of magnitude smaller than a chunk cannot exercise the thing it
        # exists to exercise.
        words_per_section = max(400, target_words // len(_SECTIONS))

        words: list[Word] = []
        clock = 0.0

        for section_index, (_, section_words) in enumerate(_SECTIONS):
            emitted = 0
            while emitted < words_per_section:
                for position, token in enumerate(section_words):
                    ends_sentence = position == len(section_words) - 1
                    start = clock
                    end = clock + per_word * 0.9
                    words.append(
                        Word(
                            text=token + ("." if ends_sentence else ""),
                            start=round(start, 3),
                            end=round(end, 3),
                            speaker="SPEAKER_00",
                        )
                    )
                    clock = end + per_word * 0.1
                    emitted += 1

                # A breath between sentences: what the chunker looks for.
                clock += 0.7

            # A longer pause between sections, where a chapter should begin.
            clock += 1.6 + ((seed + section_index) % 5) * 0.1

        return words


class WhisperXTranscriber:  # pragma: no cover - requires the model
    """
    The real transcriber (§5.2): WhisperX, for word-level alignment.

    Lazily imported. §10.3 is explicit that the 50-hour backfill runs on free
    GPU compute and is exported as a portable artifact — this must not be run
    on the API host.
    """

    engine = "whisperx"

    def __init__(self, model_size: str = "base", device: str = "cpu") -> None:
        try:
            import whisperx
        except ImportError as error:
            raise RuntimeError(
                "WhisperX is not installed. The worker falls back to the "
                "fixture transcriber, which does not produce real transcripts."
            ) from error

        self._whisperx = whisperx
        self._device = device
        self._model = whisperx.load_model(model_size, device)
        self.engine_version = model_size

    def transcribe(self, audio_ref: str, duration_sec: int) -> list[Word]:
        audio = self._whisperx.load_audio(audio_ref)
        result = self._model.transcribe(audio)

        align_model, metadata = self._whisperx.load_align_model(
            language_code=result["language"], device=self._device
        )
        aligned = self._whisperx.align(
            result["segments"], align_model, metadata, audio, self._device
        )

        return [
            Word(
                text=word["word"],
                start=float(word["start"]),
                end=float(word["end"]),
                speaker=word.get("speaker"),
            )
            for segment in aligned["segments"]
            for word in segment.get("words", [])
            if word.get("start") is not None and word.get("end") is not None
        ]
