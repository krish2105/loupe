# AI playlists — what works and what the corpus will not support

Plan ref: §11. Contract: *natural-language brief in; ordered list plus a written
rationale for the ordering out; return fewer items rather than padding with poor
matches; saved as a real playlist.*

The feature is built and every clause of that contract is implemented. Two
things about it are not good, and this is the record of both.

---

## What it does

A brief is embedded and matched against transcript chunks, one best chunk per
talk. Talks clearing an inclusion floor are ordered strongest-first, taking one
talk from each channel before any channel's second, and saved as a real playlist
with a written rationale and — per item — the timestamp where the transcript
addresses the brief.

No model is called. Composition is retrieval and ordering, so it spends nothing
against the §10.3 cost ceiling.

The rationale is templated from the result rather than generated. A model asked
to explain the ordering would produce a fluent paragraph about pedagogical
progression describing an ordering nobody computed, and the rationale is
precisely the part a reader takes on trust.

## Finding 1 — the borrowed threshold did not separate anything

The inclusion floor started as `CITATION_THRESHOLD` (0.34), on the reasoning
that "related enough to cite in an answer" and "related enough to include in a
playlist" are the same question.

Composing three briefs against the indexed corpus:

| Brief | Score range |
|---|---|
| how attention scales with sequence length | 0.644 – 0.649 |
| making inference cheap enough to deploy | 0.493 – 0.505 |
| **underwater basket weaving for beginners** | **0.363 – 0.372** |

The third cleared 0.34 across the board and produced a full eight-talk playlist
of machine-learning systems talks, presented with a confident rationale. That is
the §11.1 failure mode — a confident answer where the honest answer is "nothing
here covers this" — arriving in a feature §11.1 was not written about.

The cause is not a bad constant so much as a bad instrument. bge-m3 places
unrelated text around 0.35, so **any absolute threshold in that region sits
inside the model's own noise floor** and cannot separate on-topic from
off-topic. The assumption that the two questions shared a threshold was the
error; the threshold was only its symptom.

The floor is now 0.45 and the off-topic brief refuses. It is calibrated against
three briefs on an eight-video corpus, which is thin, so it is recorded as
provisional. The separation it relies on — 0.37 against 0.49 — is wide. The
confidence that 0.45 is the right point inside that gap is not.

## Finding 2 — the ranking is noise, and the threshold does not fix it

Look again at the on-topic row: **0.644 to 0.649**. Eight talks separated by
five thousandths.

The eight indexed videos are fixture transcripts generated from one template, so
their text is near-identical by construction. Retrieval is not choosing between
them because there is nothing to choose between. The ordering the rationale
describes — "strongest first" — is real in the code and meaningless in the
output. So is the channel spread, since every candidate is interchangeable.

Raising the floor fixed the refusal. It did nothing about this, and nothing
could: it is a property of the corpus, not of the retrieval.

This is the same limitation that ended the Phase 5 chapter-drift work and the
Phase 9 recommendation evaluation, arriving a third time from a third direction.
A synthetic corpus can demonstrate that a system is wired correctly. It cannot
demonstrate that the system is any good, and the three findings agree about
that more strongly than any one of them does alone.

## What would settle it

1. **A real corpus.** Fifty hours of genuinely different talks. Everything below
   depends on this one.
2. **Calibration against labelled briefs.** Twenty briefs — ten answerable, ten
   deliberately not — and a threshold chosen from where the two distributions
   actually separate, rather than from three observations.
3. **A relative test instead of an absolute one.** The shape of the score
   distribution distinguishes an answerable brief from an unanswerable one more
   robustly than its height does. It cannot be tried here, because on this
   corpus both shapes are flat.

## Not done: leaving the floor where it was

Two thresholds have been deliberately left untuned in this project — the Phase 7
sweep that showed 0.50 scoring a perfect 1.000, and the Phase 9 recommender that
lost to its baseline. Both were refused because moving the number would have
improved a published metric without improving the system.

This is a different case and the distinction is worth being explicit about. No
metric is being reported here. What changed is a demonstrated user-facing
failure: a request for basket weaving returned eight talks about GPU memory
bandwidth. Fixing that is not tuning to a number, and the new number is
published with its own weakness attached.
