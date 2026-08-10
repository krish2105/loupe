# Two content classes and a state machine

Loupe is a video platform where you can search inside talks, ask questions about
them, and get answers with timestamps you can click. Two decisions shaped
everything else about how it is built: the catalogue holds two kinds of video
with deliberately different capabilities, and the work that turns a video file
into something searchable runs as an explicit state machine rather than a
sequence of function calls.

This document is about those two decisions, what they cost, and where they leak.

It has since acquired a third subject. Both original decisions were made before
any media provider existed, so the boundary that was supposed to keep storage
credentials in one place was a claim rather than a constraint. Provisioning
storage tested it, and [the storage boundary](#the-storage-boundary-tested-for-real)
records what held and what had to change.

## The problem with a small catalogue

A video platform with forty videos does not look like a video platform. It looks
like a demo of one. The feed is empty after one scroll, search returns nothing
for most queries, and every screenshot has the same six thumbnails in it.

The fix that first suggests itself is to get more videos. But the intelligence
layer, which is the actual point, needs a transcript per video, and
transcription runs at roughly real time on CPU. Two thousand hours of talks is
two thousand hours of compute plus storage for the renditions. That is not a
budget problem you solve with a better plan; it is arithmetic.

So Loupe holds two classes of video and does not pretend otherwise.

**Class A, owned.** Uploaded or Creative Commons talks stored as HLS renditions,
transcribed with word-level timestamps, chunked, embedded, and indexed. Every AI
feature works on them. There are 17 of these, about 7 hours.

**Class B, referenced.** Metadata for talks that live on another platform,
ingested nightly from curated channels. Title, description, duration, channel,
publication date. No transcript, no stored media, playback handed to the source
platform's embed. There are 3,048 of these across 37 channels.

Class B makes the feed feel like a product. Class A proves the thing the product
is for. Neither one alone would do.

The uncomfortable part is that this is not a compromise invented for a portfolio
project. Every real platform has a processing backlog, a licensing tier it
cannot index, and content it links to rather than hosts. The two-class model is
what those platforms look like from the inside. Building it deliberately was
cheaper than pretending otherwise and then discovering the same thing under
deadline.

### Enforcing the asymmetry instead of remembering it

The interesting question is not how to represent two classes. It is how to stop
the difference between them from quietly eroding.

The failure mode is specific and it takes about six weeks to arrive. Someone
writes a query that joins transcript chunks to videos without filtering on
class. It works, because Class B videos have no chunks and the join returns
nothing. Later someone backfills a placeholder transcript for testing. Now the
query returns rows and the UI shows an "ask this video" button on a talk with no
transcript. Nobody notices until a demo.

Loupe pushes the rule into the schema, where it cannot be forgotten:

```sql
CONSTRAINT videos_referenced_never_processes
  CHECK (source_class <> 'referenced' OR processing_status = 'referenced_only'),
CONSTRAINT videos_owned_never_referenced_only
  CHECK (source_class <> 'owned' OR processing_status <> 'referenced_only'),
CONSTRAINT videos_referenced_has_external_id
  CHECK (source_class <> 'referenced' OR external_id IS NOT NULL)
```

A referenced video cannot enter the pipeline. An owned video cannot sit in the
terminal state that means "we do not process this." A referenced video without a
pointer to where it actually lives cannot exist at all. Twenty-one assertions in
`db/tests/constraints.sql` check these and the rest of the schema's rules on
every CI run, by attempting the violation and requiring the database to reject
it.

The API computes a capability set per video and every surface reads it rather
than inferring from the class. That indirection matters more than it looks: it
means adding a third class later changes one function, not every template that
decides whether to render an AI panel.

### Where it leaks

Two places, both visible in the product.

Search covers transcripts for Class A and titles and descriptions for Class B.
Results from the two classes are therefore not comparable, and a query that
matches a spoken sentence in one talk competes against a query that matched a
title in another. The UI marks which is which, but the ranking is still mixing
two different measurements.

And the recommendation model's content similarity feature is computed with
TF-IDF over descriptions. About 3,000 of the 3,065 descriptions are
fixture-generated and near-identical, so that feature carries almost no
information. This was a direct cause of the recommender losing to a popularity
baseline, which is documented in `docs/recommendations.md`.

## The stage machine

Turning an uploaded file into something you can ask questions about takes six
steps. Each one is slow, each one can fail, and one of them costs money.

For most of this project the first transition had nothing behind it. Transcoding
was the media provider's job, the provider was never provisioned, and every
video in the catalogue arrived already `transcoded`, pointing at somebody else's
stream. The machine described a step that had never run. It runs now, on ffmpeg,
and the description below finally matches the code.

```
uploaded → transcoding → transcoded → transcribing → transcribed
        → chunking → embedding → indexed → enriched
```

The naive implementation is a function that calls each step in order. It works
until the third step fails on video 200 of 400, at which point you have no
supported way to resume, no idea which videos got how far, and a strong
temptation to just run the whole thing again.

So state lives on the row. One enum column, `processing_status`, with a value
for each stage plus a `failed_<stage>` value for each failure, and a
`retry_count`. Nothing is inferred from the presence or absence of related rows.

That last point is the one worth arguing for. The alternative design derives
status: a video is transcribed if a transcript row exists, chunked if chunks
exist, and so on. It seems elegant and it removes a column. It also makes
"currently transcribing" and "failed halfway through transcribing" the same
state, which is exactly the distinction you need when something goes wrong at
three in the morning.

### What each step declares

```python
@dataclass(frozen=True)
class Step:
    name: str
    start: str    # the status that makes a video eligible
    running: str  # the status held while it runs
    done: str     # the status on success
    failed: str | None
```

Five steps are declared this way. A `failed` of `None` means the step degrades
rather than breaks: enrichment produces chapters and a summary, and a video
without them is still fully watchable and searchable, so a failure there returns
the video to `indexed` instead of parking it.

Chunking is worth a note. It ends at `embedding` rather than at a `chunked`
status, and embedding both starts and runs at `embedding`. This looks like a
mistake and is deliberate. Embedding models change. When one does, you want to
re-embed 100,000 chunks without re-transcribing the audio they came from, and
that requires the embed step to be independently resumable from a state the
chunker leaves behind.

### Idempotency, and why it is not optional

Every step claims a job before it runs:

```sql
INSERT INTO pipeline_jobs (video_id, stage, version, attempts, started_at)
VALUES ($1, $2::processing_status, $3, 1, now())
ON CONFLICT (video_id, stage, version) DO UPDATE
SET attempts = pipeline_jobs.attempts + 1, started_at = now(), error = NULL
```

If a finished job already exists for that `(video, stage, version)`, the claim
returns false and the step does nothing. Re-running the whole pipeline over the
whole catalogue is free for everything already done.

The `version` column is what makes reprocessing possible without deleting
history. Bump it and the same stage runs again as a new job, with the old
attempt still on record. Every generated row also stores the engine version or
model that produced it, so a model change means selectively re-indexing the
affected rows rather than rebuilding everything.

### The cost ceiling is code

Transcription is the only step that spends real money. The plan called for a
hard monthly cap on transcription minutes, enforced in the worker rather than by
discipline, and the worker reads the remaining budget before claiming a job and
refuses when it is spent.

That refusal path had a bug in it. The variable holding the cap was out of scope
in the branch that reported budget exhaustion, so the code would have raised a
`NameError` at exactly the moment the cap was hit and never at any other time. A
linter caught it. Nothing else would have, because the only test that exercises
that branch is one that deliberately exhausts the budget, and I had not written
it yet.

The general lesson is dull and correct: error paths that only fire in rare
conditions are the paths least likely to have ever run.

### Failure injection

The Phase 5 gate required that the stage machine survive forced failure
injection, not that it work when nothing goes wrong. The tests fail a step
mid-run and assert the video parks at the right `failed_` status with an
incremented retry count, that a retry resumes from the parked state rather than
from the beginning, and that a video exceeding `MAX_RETRIES` stops being
selected instead of looping.

Testing the machine rather than the work is why these tests run in
CI without a GPU, an ASR model, or a media provider. The steps are injected.

### Declining is not failing

A stage machine records two outcomes: the step worked, or the video is broken.
That is one outcome too few.

Running the pipeline against the live catalogue would have parked six healthy
videos as `failed_transcribing`. They sit at `transcoded` with a referenced
stream, so there is no source file in our storage to extract audio from; a real
recogniser handed one of those raises, and the machine faithfully records the
video as broken. It is not broken. It is not ours to transcribe.

So transcribers declare whether they need an audio file — real ones do, the
fixture does not — and the runner filters the eligible set before claiming any
jobs. The count of declined videos is reported rather than swallowed, because a
catalogue where most talks are quietly skipped is something an operator should
be told rather than left to infer.

The general shape is worth naming: a step that cannot run is different from a
step that ran and failed, and a machine with only the second concept will
mislabel the first. This was found by checking what a run *would* touch before
running it against a database holding live data, which is the only reason it is
a paragraph here rather than an incident.

## What the split between services buys and costs

Five services, split by what they are allowed to know:

| Service | Owns | Never |
|---|---|---|
| Core API | CRUD, authorisation, feed assembly | Calls a model, holds a media credential |
| Media | Upload tickets, storage signing, playlist rewriting | Anything else |
| Ingest | The nightly Class B sync, the quota ledger | Runs at request time |
| Pipeline | Transcoding through enrichment | Serves a request, holds a storage key |
| AI | Summaries, ask-video, semantic search, playlists | Verifies a session token |

The last row is the one that keeps paying. The AI service holds every prompt and
every model key and has no concept of a user. When AI playlists needed to be
saved as real playlists owned by a real person, the composition stayed in the AI
service and the write went to the core API, which already knew how to authorise
one. The AI service still does not verify tokens.

The cost is real. Composing a playlist is now an HTTP call between two services
that both talk to the same database, which is slower and adds a failure mode
that needed its own handling: the AI service being unreachable is a 503, an
error from it is a 502, and a video deleted between the retrieval query and the
write is a 409 telling you to try again.

For this scale a single process would be faster and simpler. The split earns its
keep for a different reason: the boundaries are where the rules live. "The API
never calls a model" is enforced by the API not having a model client, which is
harder to violate accidentally than a comment saying not to.

## The storage boundary, tested for real

"The media service is the only holder of provider credentials" was a claim for
eleven phases, because no provider existed. Provisioning one turned it into a
design constraint with teeth, and two decisions came directly out of it.

**The transcoder holds no storage credentials.** It has to read a source object
and write a few hundred rendition objects, so it needs signed URLs, and there
were three ways to get them: copy the keys into a second service, import the
media service's signing code, or ask. It asks, over a token-gated endpoint.

Copying would have made the claim false. Importing would have meant either
duplicating SigV4 — two implementations of a signature is two things to get
subtly wrong, and the second always drifts — or a path dependency between two
packages that both export a top-level `app` module, which does not resolve. So
the remaining option was the one that also happens to be right: a round trip per
object, in exchange for rotating the storage key touching one service and a
compromised transcoder minting URLs only while it can still reach the signer.

**The bucket is private, and the constraint improved the design.** It was
forced — the provider gates public buckets behind payment history — and a public
bucket would have been simpler: the player fetches segments directly and nothing
needs signing. That convenience is exactly the problem. A public URL works
forever, so a takedown has to delete the object because nothing else can revoke
access, and this platform accepts uploads and owes a removal that removes.

Private means playlists are rewritten on the way out. The media service fetches
the manifest, replaces every URI, and returns it; only the manifest — a few
kilobytes — crosses the process, while segments travel bucket-to-viewer
directly. Segments resolve to presigned URLs; nested playlists resolve back to
the same endpoint, because signing a child playlist's segments at the moment its
parent was fetched means a viewer who starts an hour later meets a wall of 403s.

**What the row stores is a key, not a URL.** `video_assets.hls_url` holds an
absolute URL for referenced streams and a bucket key for anything the transcoder
produced. A URL would bake the media service's hostname into every row, so
moving the service would mean rewriting the table, and a signed URL would expire
in place. The row records *what* the asset is; each service renders *where* at
the moment it answers.

That last decision cost a bug before it paid: the core API returned the key raw
for a while, and the watch page fed it straight to the player as a relative path
that resolved against the web app's own origin. The fix is a pure function with
tests, and the tests assert the media service's route rather than the shape the
mistake produced.

## Two schema decisions worth defending

**Watch events are append-only.** Every progress write inserts a row. Resume
position is computed on read as the most recent event, not stored and
overwritten. A database trigger rejects any UPDATE or DELETE.

This costs storage and makes the resume query a `DISTINCT ON` instead of a
column read. It buys a complete history of what everyone watched and how far
they got, which is the training data the recommendation model needs. The
alternative, a mutable `position_sec` on a join table, is smaller and faster and
throws that away permanently. You cannot recover a history you never recorded.

The trigger had a flaw. It blocked cascading deletes too, which meant deleting a
user account was impossible: the cascade tried to remove their watch events and
the trigger refused. Migration 0007 added a transaction-scoped opt-in,
`SET LOCAL loupe.allow_purge = 'on'`, that permits DELETE. UPDATE stays
unconditionally blocked, because there is no legitimate reason to edit a
recorded event.

**Chunks store two versions of their text.** `text_normalised` has filler words
and bracketed caption annotations stripped and whitespace collapsed, and it is
what gets embedded. `text_display` is what the speaker actually said, and it is
what a citation shows you.

Storing one and deriving the other does not work in either direction.
Normalisation is lossy, so you cannot recover the display text from it. Deriving
the normalised text at query time means running the cleaner on every chunk on
every search. The duplication is the cheap option.

## The four list surfaces are one thing

Subscriptions, History, Watch Later, and Playlists look like four features. They
are one: a user-scoped set of videos with a membership rule and an ordering.
Only those two vary.

Each is declared rather than implemented:

```python
"history": Collection(
    key="history",
    title="History",
    empty_title="Nothing watched yet",
    empty_body="Talks you watch appear here, most recent first...",
    membership_sql="""
        SELECT DISTINCT ON (w.video_id) w.video_id, w.occurred_at AS sort_key, ...
        FROM watch_events w WHERE w.user_id = $1
        ORDER BY w.video_id, w.occurred_at DESC
    """,
)
```

One loader wraps the membership query, joins the video columns, applies the
visibility filter, computes capabilities, and paginates. Adding a fifth surface
is a dictionary entry.

The payoff arrived unplanned. When AI playlists needed to show the matched
moment per item, the moment travelled through the `context` field the
abstraction already had for history's resume position, and appeared on the
existing surface. No new endpoint, no new component.

The web side mirrors this with one `CollectionSurface` component behind four
routes. Four page components would have produced four empty states, four grid
definitions, and four slightly different ideas of what a signed-out visitor
sees. That divergence is not hypothetical; it is what happens.

## What this architecture cannot tell you

Three separate pieces of work hit the same wall from three directions, and it is
worth stating plainly because the architecture looks healthier than the results
are.

Chapter detection found no boundaries in the fixture transcripts, because the
fixtures were six 40-word topics and the chunker produces 300 to 600 token
chunks. The detector was correct and the corpus was too small to have topics.

The recommendation model lost to a popularity baseline, partly because content
similarity is computed over 3,000 near-identical fixture descriptions.

AI playlist composition returns talks separated by five thousandths of a
similarity point, because the indexed transcripts came from one template and
there was nothing to discriminate between them.

Together they said something the individual documents did not: this architecture
is verified to be wired correctly and is not verified to be any good. Those are
different claims, and a synthetic corpus can only support the first.

### What changed when the corpus stopped being synthetic

Eight talks now carry real speech and real recognition output. That is a small
corpus and clean audio, so it does not settle the question — but it moved the
second claim from unsupportable to partially measured, and the first thing it
did was find a defect the architecture had been hiding.

Citation accuracy scored 0.600 on fixtures. The golden set read its expected
timestamps from chunk boundaries, and a citation returned the chunk's start
time, so the metric was checking that a citation equals the chunk start — true
by construction. Anchoring expected timestamps on the sentence that actually
answers the question dropped it to 0.053, and the cause was not retrieval. The
system promised a jump to *the moment* and returned the top of a three-minute
passage. The word-level timestamps needed to do better had been a hard schema
requirement from the start, and nothing had ever read them. Reading them, and
picking the answering sentence by embedding rather than by word overlap, took it
to 0.421 — eight times better than what the 0.600 was concealing, and still not
good, since a ±5s tolerance is roughly one sentence of speech.

This is the useful lesson of the whole project, and it is not about video. **A
metric computed over data you generated will confirm the assumptions you built
into both.** The stage machine, the constraints, the service boundaries and the
idempotency were all genuinely right; the thing that was wrong sat in the gap
between what a citation promised and what it returned, and no amount of
architectural care would have surfaced it. Only a corpus the architecture did
not author could.

What remains unmeasured is still substantial: real recordings with accents and
crosstalk, a catalogue large enough for retrieval precision to mean something,
and any interaction data at all. Every quality number in this project is
reported with the caveat that applies to it, because the alternative is
reporting a number that means nothing and hoping nobody asks.

## Reading the code

- Content classes and constraints: `db/migrations/0002_core_content.sql`
- Channel ownership: `db/migrations/0013_channel_ownership.sql`
- Schema assertions: `db/tests/constraints.sql`
- Stage machine, and declining vs failing: `services/pipeline/app/stages.py`,
  `services/pipeline/app/run.py`
- Transcoding and the rendition ladder: `services/pipeline/app/transcode.py`,
  `services/pipeline/app/ladder.py`
- Storage signing, written out rather than imported: `services/media/app/s3.py`
- Playlist rewriting for a private bucket: `services/media/app/playlist.py`
- Key-to-URL rendering: `services/api/app/playback.py`
- Citing a moment rather than a passage: `services/ai/app/moments.py`
- Cost ceiling: `services/pipeline/app/budget.py`
- Collection abstraction: `services/api/app/routers/collections.py`
- Retrieval and the refusal threshold: `services/ai/app/retrieval.py`
