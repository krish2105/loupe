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

## Offline downloads

Built, after being declined once. The reasoning for declining conflated two
things: ADR 0003's rule is about the *class of content*, and the schema can
enforce exactly that. Class A is what Loupe owns; Class B is referenced and
never stored. So downloads are constrained to Class A by a trigger in migration
0012 rather than being refused wholesale in a comment. The demo catalogue's
media being a developer test stream is a fixture limitation, recorded with the
others, not a reason to leave a capability unbuilt.

**What gets stored is audio only.** On the reference stream the audio rendition
is 12MB against 27MB for the smallest video one, and this is audio mode.
Downloading video for a podcast is storing something nobody is going to look at.

Three cache entries per episode: a rewritten master playlist offering only the
audio rendition, the audio rendition's own playlist unchanged, and the file its
byte ranges are cut from.

**The rewritten master is the part that makes it work.** Serving the original
master offline would let the player pick a video rendition that was never
stored, and that failure reads as a broken download rather than a missing one.
So the stored master offers exactly one variant.

Which is also why the service worker is network-first for media, not
cache-first. The rewritten master served while online would silently cap every
stream at audio quality on a page showing a video player. Online gets the real
manifest; only a failed fetch falls back.

**Byte ranges are sliced on read.** This stream, like every fragmented-MP4 HLS
stream, addresses one file by range rather than shipping separate segments.
Cache Storage matches on URL alone, so a ranged request would otherwise get the
whole 12MB file back with a 200, which hls.js cannot use. The worker reads the
stored entry, cuts the range out, and returns a 206 with the right
`Content-Range`. That costs a read per segment instead of holding a hundred
near-duplicate cache entries — about one 12MB read per six seconds of playback,
which is nothing, and the alternative risks a key that never matches.

The download runs in the page, not the worker. Cache Storage is available in
both, and doing it in the page makes progress a callback, cancel an
`AbortController`, and failure a rejected promise on the button that started it.
The worker's only job is serving what the page put there.

**Verified against an unreachable host**, which is the only way to make the
network branch actually fail on demand:

```
full request        200, 1000 bytes from cache
bytes=10-19         206, Content-Range: bytes 10-19/1000, first byte 10, last 19
bytes=-4            206, 4 bytes, correct suffix
```

The stored master came back as the one-variant rewrite and the audio file at
12,132,238 bytes, matching the CDN's `Content-Length`.

One thing not fully explained: the first download attempt failed with a generic
error while an older service worker was still being replaced, and has not
reproduced since. The new worker's activate handler preserves the media cache
where the old one swept every cache but the shell, which is the most likely
cause and is the behaviour that was wanted anyway. Recorded rather than
presented as diagnosed.

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

## The full-screen view

The player bar expands to a full-screen listening surface, from the title block,
which is the target people already reach for.

**The transcript is the hero, not artwork.** In a music app this surface is
dominated by cover art, because cover art is what a track has. An episode here
has none — shows carry an avatar, episodes carry nothing — so a large square
would be a placeholder occupying the best space on the screen. The transcript
takes it instead: the words, timed, following the audio, and clickable to seek.
ADR 0003 argued spoken audio was the right catalogue because every capability
already built applies to it, and this is what that looks like given the whole
screen.

**There is no second media element.** The one in the bar keeps playing and this
view reads the same store, which is the only reason expanding does not interrupt
the audio.

**The page behind is made `inert`** rather than wrapped in a hand-written focus
trap. One attribute removes it from the tab order and from assistive technology,
which is what a focus trap is imitating. Focus moves to the collapse button on
open and Escape closes.

The expand target is a button, not a link. The episode page is a different thing
from the player, and putting navigation behind the gesture that everywhere else
opens the player would send people somewhere they did not ask to go. The episode
page is one tap further in, from the title inside the view.

Playback speed moved into the player store while building this. Two surfaces now
show it, and a component holding its own copy is how they end up disagreeing.
Moving it fixed a bug that had been there since the bar was built: loading a new
source resets the element to 1×, so the chosen speed was silently lost on every
track change. It also exposed a second one — the store's change check listed
every field by name and did not know about the new one, so rate changes were
published to nobody.

**Two things this surfaced in the transcript view**, both of which were wrong on
the episode page too:

The follow-along guard was a boolean. A smooth `scrollTo` emits scroll events
for its whole duration, so the flag absorbed the first and every one after it
read as a person scrolling. Following switched itself off on the first automatic
scroll, every time. The symptom, once the full-screen view made it obvious: a
transcript sitting at 0:00 while the audio played at nine minutes. It is a
timestamp window now, and a large jump scrolls instantly rather than easing for
seconds across a forty-minute transcript.

The list capped itself at `60dvh`. Correct on the episode page, where it sits in
a scrolling document; wrong inside a sheet whose parent already constrains the
space, because "scroll the active line a third of the way down" then computed a
third of the list's height rather than a third of the visible area, and put the
active line off screen.

Verified in a browser: expanding leaves exactly one media element and does not
pause; the page behind goes inert; the transcript lands on the playing line with
it on screen; Escape and the collapse button both restore the page, clear the
scroll lock, and leave the audio running.

## The sleep timer

Shows a running countdown in the player bar, in seconds, with one press to
cancel.

The rule underneath it: **remaining time is computed from a deadline, never
decremented.** Those look equivalent and are not. A sleep timer spends almost
its whole life in a backgrounded tab, where browsers throttle timers to roughly
one call a minute, and every skipped tick is a minute a decrementing counter
never subtracts. A fifteen-minute timer would still read eleven after twenty.
Recomputing from a deadline is correct however few times it runs.

Three smaller decisions:

- Seconds are always displayed. A counter reading "14 min" for a full minute
  before jumping to "13 min" gives no sign it is running, which is the one thing
  a countdown is for.
- Ticks are aligned to the next whole second rather than fired every 1000ms. A
  flat interval drifts a few milliseconds per tick and eventually skips a
  number, which reads as a stutter.
- The timer also checks when the tab becomes visible again, because a throttled
  tab can pass its deadline long before the next tick. The audio has stopped by
  the time anyone looks, rather than playing on until a late timer notices.

It is its own component so a per-second tick re-renders eleven characters
instead of the transport controls. The bar already re-renders on every
`timeupdate`, so the saving is small — but the play button has no business
re-rendering because a clock moved.

Pausing rather than stopping means the position survives and the playhead
persistence picks it up.

Verified in a browser: the countdown read 15:00 and then 14:57 three seconds
later, and pushing the clock twenty minutes past a fifteen-minute deadline and
firing a visibility change paused the audio and cleared the timer — which is the
backgrounded-tab case the deadline design exists for.

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
| Downloading an episode | **Verified in a browser** — 12MB audio rendition, three cache entries |
| Offline serving and range slicing | **Verified in a browser** against an unreachable host |
| Playing a downloaded episode with the network truly down | **Not verified** — needs a real offline device |
| Sleep timer countdown and firing | **Verified in a browser**, including the backgrounded-tab path |
| Playhead restored after reload | **Verified in a browser**, mid-episode and near the end |
| Full-screen view | **Verified in a browser** — one media element, inert page, following transcript, Escape |

The pattern from every previous phase holds: what could be made pure was made
pure and tested, and what needs a device says so.
