# ADR 0001 — Media provider

**Status:** Accepted — Bunny Stream, 9 Aug 2026. §5.2 stands unamended.
**Amends:** Nothing. The re-evaluation was requested and confirmed the original choice.

## Context

The plan selected Bunny Stream and recorded the alternatives it rejected:
Cloudflare Stream (per-minute pricing worse at this library size), Mux (best
analytics, highest cost), and self-hosted FFmpeg transcoding (weeks of work for
zero portfolio signal).

A re-evaluation against free options was requested. §18.7 requires an explicit
recorded decision to change a settled choice, which is what this document is.

Requirements, taken from the plan rather than invented:

- Adaptive bitrate from an HLS manifest (§9.1 — never force a resolution)
- Signed playback URLs, even for openly licensed content (§5.1)
- 50 hours hosted (§15 caps the owned library there)
- Inside the sub-$10/month envelope (§14)

## Options

Sized at 50 hours of 720p (~25 GB) with roughly 10k monthly views.

| Option | Monthly | Transcoding | Signed URLs | ABR | Card required |
|---|---|---|---|---|---|
| **Bunny Stream** | ~$4–6 | Included | Token auth | Yes | Yes |
| **Cloudflare Stream** | ~$15 storage + delivery | Included | Yes | Yes | Yes |
| **Mux** | $20+ after trial credits | Included | Yes | Yes | Yes |
| **Supabase Storage** | $25 (Pro; 25 GB exceeds the 1 GB free tier) | None | Yes | Only if self-packaged | Yes |
| **Cloudflare R2 + own ffmpeg ladder** | **~$0.40** (25 GB at $0.015/GB, **zero egress**) | Do it yourself | Presigned S3 URLs | Yes, if you build the ladder | Yes |

## Finding

**There is no genuinely free option at 50 hours.** Every candidate requires a
payment method. The request was for a free alternative and the honest answer is
that one does not exist at this scale; what exists is a much cheaper one.

R2 is roughly ten times cheaper than Bunny because R2 charges no egress fees at
all, and delivery — not storage — is what costs money on a video platform.

The §5.2 objection to self-transcoding does not transfer cleanly to R2. That
objection was aimed at *building a transcoding service*: queues, workers, retry
semantics, weeks of work. Loupe already has that machinery, because §5 specifies
a pipeline worker with an idempotent stage machine for transcription. Adding an
ffmpeg HLS-ladder step to a worker that already exists is roughly a day, not
weeks. The transcode step is already in the stage machine (§10.1); only its
implementation changes from "consume the provider webhook" to "run ffmpeg".

## Where this genuinely costs something

- **HLS packaging bugs are subtle.** Segment duration, keyframe alignment across
  renditions, and manifest correctness all fail quietly and only on some players.
  Bunny makes that someone else's problem.
- **No thumbnail sprite for free.** §9.1 requires sprite-sheet hover preview on
  the scrubber, which Bunny generates. With R2 that becomes another ffmpeg step.
- **§5.2's stated rationale disappears.** "Transcoding included at no per-minute
  charge" was the reason Bunny won. Choosing R2 means the plan's own comparison
  no longer supports the plan's own choice, which has to be said out loud in the
  README rather than quietly reversed.

## Recommendation

**Bunny Stream, unless the ~$4/month is itself the objection.**

Both fit the §14 envelope, so cost is not the deciding factor — $4 and $0.40 are
the same decision against a $10 ceiling. What differs is risk and attention.
Bunny buys back the sprite generation and the packaging correctness, and the
scarce resource in a 12-week plan with a §15 risk register full of timeline
pressure is attention, not dollars.

Take R2 if adding a card to Bunny is unacceptable, or if demonstrating a
hand-built HLS ladder is itself a portfolio goal — it is a legitimate one, just
not one the plan claimed.

## Decision

**Bunny Stream**, as originally specified. The re-evaluation was worth running —
it established that R2 is genuinely an order of magnitude cheaper and that the
"weeks of work" objection was aimed at a different problem than the one we have
— but neither of those changes the outcome against a $10 ceiling, and Bunny buys
back sprite generation and packaging correctness.

The R2 analysis is retained rather than deleted. If the media bill ever becomes
the constraint, or if a hand-built HLS ladder becomes a portfolio goal in its
own right, the working is already done.

## Consequence for Phase 1

Bunny is not provisioned yet, so Phase 1 splits:

- **Buildable now:** the custom player, controls, chapter-segmented scrubber,
  keyboard bindings, resume, and progress writes — verified against a public
  multi-rendition HLS stream.
- **Blocked on credentials:** upload signing, the transcode webhook, and
  playback URL signing.

The §5 media-service boundary is what makes that split clean: the core API never
holds provider credentials, so the player never learns which provider produced
its manifest.
