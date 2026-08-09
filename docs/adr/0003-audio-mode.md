# ADR 0003 — Audio mode

**Status:** Accepted in principle, 9 Aug 2026. Scheduled after Phase 10.
**Adds to:** §3 scope. Does not amend §3.2 — audio was never excluded.

## The decision

Loupe gains an audio-first mode: spoken audio (podcasts, interviews,
conference recordings, lectures) with the playback controls of a music app —
persistent queue, shuffle, repeat, radio, background playback, OS media
controls, offline downloads, and a time-synced transcript view.

Sequenced **after** Phase 10, so the plan reaches a shippable, documented state
first. Music becomes a clearly-scoped follow-on rather than an unfinished
eighth thing.

## Why spoken audio rather than music

Real music requires licensing Loupe does not have. The two honest alternatives
were CC-licensed music or spoken audio, and they are not equivalent:

CC music is legally streamable and would make a genuine music player. But CC
catalogues are overwhelmingly instrumental, and instrumental tracks have no
transcript — so the semantic layer, which is the entire differentiator, would
do nothing. It would be a competent player bolted to a smart product.

Spoken audio inverts that. Every capability already built applies directly:
search inside, ask it questions, jump to the moment, chapters, summaries. A
podcast episode is exactly the shape of content this product was designed for
and happens not to have video.

The time-synced view makes the point. In a music app it is a lyrics panel and
needs licensed lyrics data. Here it is the transcript, with word-level
timestamps Loupe already stores, and every line is clickable to seek.

## Scope

**In:**

- Persistent mini-player surviving navigation — the player store moves to the
  root layout
- Queue: play next, add to queue, reorder, clear
- Shuffle, repeat one/all, autoplay next
- Radio from a seed, built on `video_similarity`, which §6.4 already defines
  and nothing currently uses
- Media Session API: lock-screen artwork, hardware media keys, OS controls
- Offline playback as a PWA with a service worker
- Time-synced transcript view that follows playback and seeks on click
- Sleep timer, playback speed, persisted volume

**Out:**

- The paywall. "Premium" in the products this borrows from means a paid tier,
  and §3.2 excludes monetisation. The features are simply on. There are no ads
  to remove, so ad-free is the default rather than a benefit.
- Licensed music and licensed lyrics.
- A native mobile app, per §3.2.

## What will not work, stated now

**Sustained background audio on iOS Safari is unreliable.** §3.2 excludes
native apps, so a PWA is the ceiling. Media Session delivers lock-screen
controls and metadata, and audio does continue during in-app navigation — but
iOS suspends web audio aggressively once the browser is backgrounded, and no
amount of implementation changes that. This will be a README limitation, not a
surprise found in week three.

**Offline downloads only work for content Loupe owns or that is openly
licensed.** Caching licensed content without DRM is not a technical gap to
close.

## Consequences

The player store was built framework-free in week 1 precisely so it could be
consumed by things that did not exist yet (§5.1). Moving it to the root layout
is the change that makes background playback possible, and it is small because
of that decision — which is worth noting as evidence the early abstraction paid
for itself.

The data-model question is answered in
[`audio-data-model.md`](../design/audio-data-model.md).
