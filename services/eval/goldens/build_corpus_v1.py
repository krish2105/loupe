#!/usr/bin/env python3
"""
Build the golden set for the real corpus.

    DATABASE_URL=... uv run python services/eval/goldens/build_corpus_v1.py

Questions are written here, from the topics, by someone who wrote the scripts
but is deliberately not reading the transcripts while writing them. That is the
first mistake `retrieval-eval` in the corpus itself describes: write a question
after reading a passage and you reuse its vocabulary without noticing, then
measure lexical overlap while believing you measured semantic retrieval. So the
questions below use ordinary phrasing — "why does the first token cost more" —
rather than the script's own words.

Timestamps are not written here. Each case names an anchor phrase, and this
resolves it against the *actual* transcript's word timings, so an expected
timestamp is where the answer genuinely is in the audio rather than where
anyone guessed. If an anchor cannot be found, the case is emitted without a
timestamp rather than with a wrong one.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://localhost:5432/loupe_eval")
OUT = Path(__file__).parent / "corpus-v1.json"

# (id, category, question, slug, anchor, should_refuse)
#
# The anchor is a distinctive phrase from the spoken script, used only to locate
# the moment. It is never shown to the retriever.
#
# Several anchors are not the phrase originally written, because the
# transcriber did not hear that phrase. "ninety fifth" became "95th", and
# "load balancers route to it" became "load balances rude to it" — a real
# recognition error on clean synthesised speech, which is a useful reminder of
# what the 4.8% word error rate is made of. Anchors are chosen from what the
# transcript actually says, since that is what a citation has to land in.
CASES: list[tuple] = [
    # --------------------------------------------------------------- factual
    ("c01", "factual", "why does generating the first token cost more than later ones",
     "kv-cache", "recomputing the keys and values", False),
    ("c02", "factual", "what limits how many people you can serve at once",
     "kv-cache", "becomes the thing that limits", False),
    ("c03", "factual", "how is memory handled like an operating system",
     "kv-cache", "exactly like virtual memory", False),
    ("c04", "factual", "why does dropping to four bits break things",
     "quantisation", "The reason is outliers", False),
    ("c05", "factual", "what makes a small number of channels a problem",
     "quantisation", "magnitudes orders of magnitude larger", False),
    ("c06", "factual", "when does guessing ahead stop paying off",
     "speculative-decoding", "the draft model's own cost exceeds", False),
    ("c07", "factual", "how can several tokens be checked at once",
     "speculative-decoding", "verifying a sequence in parallel", False),
    ("c08", "factual", "why do fixed groups of requests waste hardware",
     "continuous-batching", "generation lengths vary wildly", False),
    ("c09", "factual", "what happens when one request runs much longer than the rest",
     "continuous-batching", "the whole batch occupies the device", False),
    ("c10", "factual", "how do you tell whether you are limited by maths or memory",
     "roofline", "arithmetic intensity", False),
    ("c11", "factual", "why did a much faster card change nothing",
     "roofline", "the arithmetic was never the constraint", False),
    ("c12", "factual", "what is the most common way to fool yourself when testing search",
     "retrieval-eval", "writing the evaluation questions after reading", False),

    # ------------------------------------------------- deep in a long talk
    # The point of these. The six short talks are each a single chunk, so a
    # citation in them can only ever point at t=0 and the metric measures
    # nothing. `serving-architecture` and `attention-variants` chunk twice, so
    # an answer drawn from their second half must cite the second chunk — which
    # is the first time in this repository that a citation has had somewhere
    # wrong to land.
    ("d01", "factual", "what should you watch instead of average latency",
     "serving-architecture", "report time to first token separately", False),
    ("d02", "factual", "what goes wrong when a replica restarts",
     "serving-architecture", "it receives a burst that fills its cache", False),
    ("d03", "factual", "which failure produces no alert at all",
     "serving-architecture", "The fourth is silent degradation", False),
    ("d04", "factual", "what happens if a client reads the response too slowly",
     "serving-architecture", "applies back pressure all the way", False),
    ("d05", "factual", "how much memory does one token of context cost",
     "attention-variants", "about half a megabyte per token", False),
    ("d06", "factual", "what breaks when converting a checkpoint carelessly",
     "attention-variants", "Naive truncation does not", False),
    ("d07", "factual", "which part of the model do these variants not help with",
     "attention-variants", "none of these variants fix", False),

    # ---------------------------------------------------- cross-video
    # Impossible on the fixture corpus, where every transcript was identical.
    # Each of these is answered in one talk and touched in passing by another,
    # so retrieval has to distinguish "about it" from "mentions it".
    ("x01", "cross_video", "which talk is actually about memory bandwidth",
     "roofline", "memory bandwidth", False),
    ("x02", "cross_video", "where is batching explained rather than mentioned",
     "continuous-batching", "Continuous batching fixes this", False),
    ("x03", "cross_video", "which talk explains caching keys and values",
     "kv-cache", "The key value cache stores them", False),
    ("x04", "cross_video", "where is measuring a system properly discussed",
     "retrieval-eval", "held out set with negatives", False),

    # ---------------------------------------------------------- out of scope
    ("o01", "out_of_scope", "what is the capital of France", None, None, True),
    ("o02", "out_of_scope", "who won the world cup in 2022", None, None, True),
    ("o03", "out_of_scope", "write me a poem about the sea", None, None, True),
    ("o04", "out_of_scope", "what is the speaker's salary", None, None, True),
    ("o05", "out_of_scope", "how do I train a diffusion model", None, None, True),

    # ------------------------------------------------------------ adversarial
    # Plausible, on-topic, and not answered anywhere in the corpus. This is the
    # category the fixture run failed: 4 of 8 decided correctly.
    ("a01", "adversarial", "what throughput did they measure on an H100", None, None, True),
    ("a02", "adversarial", "which company funded this research", None, None, True),
    ("a03", "adversarial", "what learning rate did they use for training", None, None, True),
    ("a04", "adversarial", "how much did the training run cost in dollars", None, None, True),
    ("a05", "adversarial", "what was the exact accuracy after quantising to two bits",
     None, None, True),
    ("a06", "adversarial", "which conference was this talk given at", None, None, True),
    ("a07", "adversarial", "what does the speaker say about ternary weights", None, None, True),
    ("a08", "adversarial", "how many engineers worked on the scheduler", None, None, True),
]


def words_for(slug: str) -> tuple[str, list[dict]]:
    raw = subprocess.run(
        ["psql", "-t", "-A", "-F", "\x1f", DATABASE_URL, "-c",
         "SELECT v.id::text, t.segments::text FROM transcripts t "
         f"JOIN videos v ON v.id = t.video_id WHERE v.external_id = 'corpus:{slug}';"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    if not raw or "\x1f" not in raw:
        raise SystemExit(f"no transcript for {slug}. Run the pipeline first.")

    video_id, segments = raw.split("\x1f", 1)
    return video_id, json.loads(segments)


def find_anchor(words: list[dict], anchor: str) -> float | None:
    """The start time of the first word of `anchor`, or None."""
    target = re.sub(r"[^a-z0-9 ]", "", anchor.lower()).split()
    spoken = [re.sub(r"[^a-z0-9]", "", w["w"].lower()) for w in words]

    for i in range(len(spoken) - len(target) + 1):
        if spoken[i : i + len(target)] == target:
            return round(float(words[i]["s"]), 1)

    # Anchors are taken from the script; ASR may have heard a word differently.
    # A looser match on the first three words is enough to locate the moment.
    if len(target) >= 3:
        head = target[:3]
        for i in range(len(spoken) - 2):
            if spoken[i : i + 3] == head:
                return round(float(words[i]["s"]), 1)
    return None


def main() -> int:
    cache: dict[str, tuple[str, list[dict]]] = {}
    cases, unresolved = [], []

    for case_id, category, question, slug, anchor, should_refuse in CASES:
        case: dict = {
            "id": case_id,
            "category": category,
            "question": question,
            "should_refuse": should_refuse,
        }

        if slug and anchor:
            if slug not in cache:
                cache[slug] = words_for(slug)
            video_id, words = cache[slug]

            start = find_anchor(words, anchor)
            case["video_id"] = video_id
            if start is not None:
                case["expected_start_sec"] = start
                case["note"] = f"Anchored on {anchor!r} in {slug}."
            else:
                unresolved.append((case_id, slug, anchor))
                case["note"] = (
                    f"In {slug}; no timestamp because {anchor!r} was not found "
                    "in the transcript."
                )

        cases.append(case)

    OUT.write_text(
        json.dumps(
            {
                "version": "corpus-v1",
                "corpus": "groq-whisper",
                "note": [
                    "Authored against six talks with real speech, transcribed by",
                    "whisper-large-v3-turbo. This is the first golden set in this",
                    "repository written against transcripts rather than fixtures.",
                    "",
                    "What it can measure that fixture-v1 could not:",
                    "",
                    "  Cross-video comparison. The fixture corpus had one transcript",
                    "  repeated, so the category was defined as empty. Six distinct",
                    "  topics make it real, and several talks mention each other's",
                    "  subjects in passing so retrieval must distinguish 'about it'",
                    "  from 'mentions it'.",
                    "",
                    "  Retrieval against varied vocabulary. Fixture text was small and",
                    "  repetitive, which flattered retrieval.",
                    "",
                    "What it still cannot measure:",
                    "",
                    "  Real-world speech. The audio is synthesised, so it is clean —",
                    "  no accents, no crosstalk, no room, no disfluencies, no speaker",
                    "  changes. A conference recording has all of those and every one",
                    "  hurts. These numbers are an upper bound.",
                    "",
                    "  Scale. Six talks is a small corpus and precision@5 over it is a",
                    "  generous measurement, exactly as the retrieval-eval talk in the",
                    "  corpus says. The question count is reported with every score.",
                    "",
                    "Questions were written from the topics, not by reading the",
                    "transcripts. Timestamps were resolved against real word timings.",
                ],
                "cases": cases,
            },
            indent=2,
        )
        + "\n"
    )

    anchored = sum(1 for c in cases if "expected_start_sec" in c)
    print(f"wrote {OUT.name}: {len(cases)} cases, {anchored} with real timestamps")
    for case_id, slug, anchor in unresolved:
        print(f"  no anchor for {case_id} in {slug}: {anchor!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
