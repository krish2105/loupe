# Audio mode — what shipped, and what did not

Plan ref: [ADR 0003](adr/0003-audio-mode.md), scheduled after Phase 10. Data
model: [audio-data-model.md](design/audio-data-model.md).

Gate I set for it: *an episode plays from a bar that survives navigation, with a
working queue and a transcript that follows the audio and seeks on click.*

**Met.** Verified in a browser: playback continued across a client-side
navigation from `/listen` to an episode page, at 8.5 seconds and still running.

---

## The part that was already paid for

§5.1 asked for a framework-free player store in week one, built before anything
consumed it, on the argument that retrofitting one later turns citation-seek
into prop drilling. That argument was about the AI panel. The bill it actually
covered was this: moving the media element out of the video page and into a bar
in the root layout took one line in the layout and one deletion in the watch
page. Nothing that reads playback state changed, because none of it ever knew
where the element lived.

The queue needed one addition — `onEnded`, so it can advance without the media
element being public. It is a subscription rather than a getter, because "the
media reached its end" is an event and the snapshot is a state, and a queue that
inferred the end by watching `currentTime` approach `duration` would be
unreliable at the boundary and silent on a stream whose duration is unknown.

The element is still private. A feature designed eleven phases later consumes
playback without touching the DOM, which is the return on the early
abstraction stated concretely rather than as a principle.

## Schema: one column

`content_kind` on `videos`, defaulted to `'video'`, so every existing row was
correct without a backfill and every existing query kept working. No parallel
tracks/albums/artists tables.

Of the nine surfaces audio mode needs, eight required no schema change:
now-playing, queue, show page, episode page, library, radio, transcript, and
search inside all run on rows and tables that already existed. The design note
predicted that; building it confirmed it.

The one place it showed: the comments component, the AI panel, and the channel
page all appear on the episode page unchanged.

## Two things that were built and then rebuilt

**The queue started as React state and the compiler was right to reject it.** A
queue restored from `localStorage` is external state: it exists before React
renders, it outlives every component, and seeding React state from it in an
effect means the first render is wrong and the second one corrects it. It is now
a plain class behind `useSyncExternalStore`, the same shape as the player store
beside it.

**The transcript view used retrieval chunks, and that was wrong on screen.**
Chunks are 300 to 600 tokens (§10.2) because that is how much context a question
needs answering from. As a reading unit on a forty-minute episode, that is three
and a half minutes of text per line. A "time-synced" transcript whose smallest
unit is three minutes is not synced to anything.

Rebuilt on the word timings the pipeline already stores, grouped into lines at
sentence ends with a length cap for speech that runs on without punctuation, and
broken at every speaker change. The same episode went from 13 walls of text to
340 readable lines.

§11.1 calls word-level ASR non-negotiable because citation accuracy depends on
it. This is the second feature that turned out to depend on it, and it was not
foreseen when that requirement was written.

## The queue rules, and why they are pure functions

`queue-policy.ts` holds shuffle, repeat, advance, previous, insert, reorder, and
remove as pure functions over plain data, tested by 26 cases. The rules are
small and wrong in ways nobody notices until the fourth track.

The one decision everything follows from: **shuffle is an ordering, not a random
pick.** A player that picks randomly on every advance can play the same track
twice in a row and cannot implement "previous" at all.

Three more that are only obvious once written down:

- Turning shuffle on mid-episode must not change what is playing. The current
  track moves to the front of the new order.
- Repeat-one repeats when a track *ends* and is ignored when someone presses
  next. Someone pressing next wants the next track; getting this backwards
  makes the button look broken.
- Previous goes back a track in the first five seconds and restarts the current
  one after that. Without it, pressing previous halfway through a forty-minute
  episode to hear something again takes you to the wrong episode.

Play-next inserts into the play order rather than the item list, which is the
only way it can mean "next" while shuffle is on.

## Radio

Built on `video_similarity`, a §6.4 table defined in Phase 0 that nothing used
until the Phase 9 recommender populated it. It is content similarity, so radio
is neighbours-of-neighbours, and the UI says "similar episodes" rather than "for
you". Calling it personalised would be the overclaim `docs/recommendations.md`
spends a page refusing to make.

It falls back to the same show when an episode has no neighbours — which is the
case for anything indexed since the similarity job last ran, including every
episode here.

## What was not built, and why

**Offline media downloads.** ADR 0003 scoped them and they are not here. Every
piece of media in the catalogue is a third-party reference stream, and the ADR
is explicit that offline downloads only work for content Loupe owns or that is
openly licensed, calling that a licensing fact rather than a technical gap.
Caching those segments anyway so the feature demos well is exactly what that
sentence rules out.

What did ship: the app is installable, and a service worker keeps the shell
available offline with a page that says what is and is not possible. The
`downloads` table was written into the migration and then removed before
committing — a table nothing writes to is a claim that something does.

**Sustained background audio on iOS.** ADR 0003 predicted this and it is worth
repeating rather than burying: Safari suspends web audio aggressively once the
browser is backgrounded, Media Session delivers the controls and metadata but
not the background execution, and §3.2 rules out a native app. Audio does
continue during in-app navigation, which is what was verified.

## The playhead

Positions are saved per episode and restored on reload, so returning to a
forty-minute episode does not mean scrubbing for the place you had reached.
Per episode rather than one global playhead, which also makes switching to
something else and coming back work.

It reuses two things rather than inventing them. `ProgressReporter` already
decides when a position is worth writing — every ten seconds, immediately after
a seek, never the same second twice — and that judgement is the same one whether
the destination is the API or `localStorage`. And the §9.1 thresholds are the
same: under ten seconds is not worth resuming to, and past 95% lands on the
sign-off.

Those thresholds now exist in two places, in the API and in
`resume-policy.ts`, and that duplication is deliberate. The API's copy answers
"where is this signed-in person, on any device" and needs a round trip. This one
answers "where was this tab", has to be instant, and has to work for someone who
never signed in. They must agree, because the same episode resuming to two
different places depending on which path restored it is worse than either rule
alone.

Three decisions worth stating:

- Restoring does not start playback. Browsers block autoplay without a gesture
  anyway, but the position is the useful part and resuming into sound nobody
  asked for is not.
- The restore waits for metadata, because the "effectively finished" test needs
  a duration to compare against. The player store holds a seek requested before
  metadata (§5.1), so waiting costs nothing and makes the decision correct.
- Positions survive clearing the queue. Emptying a queue means "not these,
  next", not "forget where I was in the episode I was halfway through".

Finishing an episode forgets its position, so replaying it does not start on the
credits.

Verified in a browser, both ways: an episode left at 248 seconds of 600 came
back at 248; the same episode left at 592 of 600 came back at zero.

## Verified, and not

| | |
|---|---|
| Playback survives client-side navigation | **Verified in a browser** |
| Transcript follows playback and seeks on click | **Verified in a browser** |
| Queue rules | 26 unit tests |
| Transcript line grouping | 9 unit tests |
| Active-line selection | 6 unit tests |
| Media Session on a lock screen | **Not verified** — needs a phone |
| Hardware media keys | **Not verified** |
| Service worker offline behaviour | **Not verified** — needs a build, not a dev server |
| Sleep timer firing | **Not verified** — the shortest option is 15 minutes |
| Playhead restored after reload | **Verified in a browser**, mid-episode and near the end |

The pattern from every previous phase holds: what could be made pure was made
pure and tested, and what needs a device says so.
