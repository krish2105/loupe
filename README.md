# Loupe

**A video platform for AI and machine learning talks, with a semantic layer.**

Search *inside* a talk, ask it questions and get answers that cite the exact
moment, and land on that moment with one click. Built on an owned catalogue,
because transcripts are what every interesting feature here depends on.

> **Status: every phase in the plan is built, plus audio mode and its own media
> pipeline.** [ADR 0003](docs/adr/0003-audio-mode.md) scheduled audio mode after
> the roadmap; that is built. Beyond the plan, the platform now transcodes,
> transcribes and serves its own video — see [Owning the
> media](#owning-the-media). Gates are reported individually below with what is
> missing, and nothing is rounded up. See [gate status](#gate-status).
>
> **What changed the honesty of this document:** the catalogue used to point at
> a test stream with no speech, so every transcript was fixture output and every
> metric described nothing. Eight talks now carry real audio, transcribed by
> whisper-large-v3-turbo, playing from storage this project owns. That is a
> genuine step and a bounded one — the speech is synthesised, so it is far
> cleaner than any recording of a real room, and eight talks is a small corpus.
>
> The first thing the real corpus did was expose a defect the fixture metrics
> had been hiding for months. That story is in [Evaluation](#evaluation), and it
> is the most useful thing here.

---

## Why an owned catalogue

The obvious approach — build on a third-party video API — cannot work here. The
daily quota is 10,000 units and a single search call costs 100, which is about
100 searches a day. More importantly, that API does not expose transcripts at
all, and every AI feature in this project depends on transcripts.

So Loupe owns its catalogue, and treats that as an architectural fact rather
than a workaround. Two content classes with genuinely different capabilities:

| | **Class A — owned** | **Class B — referenced** |
|---|---|---|
| Transcript | Yes, word-level timestamps | No |
| Playback | Custom player | Third-party embed |
| AI features | All six | Metadata only |
| Search | Full-text + semantic over chunks | Title, description, tags |
| Purpose | Depth | Breadth |

The asymmetry is enforced by the database, not by convention. A Class B video
physically cannot acquire a transcript, an embedding, or a media asset — the
constraints reject it. See [`db/tests/constraints.sql`](db/tests/constraints.sql).

## How it fits together

```
                    ┌──────────────────────────────────────┐
   browser ───────► │  web/   Next.js 16, App Router       │
                    │         session, all UI, SSR reads   │
                    └───┬─────────────┬────────────────┬───┘
                        │             │                │
              ┌─────────▼───┐  ┌──────▼──────┐  ┌──────▼───────┐
              │ services/   │  │ services/   │  │ services/    │
              │ api  :8010  │  │ ai   :8031  │  │ media :8002  │
              │             │──►             │  │              │
              │ CRUD, auth, │  │ summarise,  │  │ upload       │
              │ feed, lists │  │ ask, search,│  │ tickets,     │
              │             │  │ playlists   │  │ playlist     │
              │ never calls │  │ never sees  │  │ signing —    │
              │ a model     │  │ a user      │  │ the only     │
              └──────┬──────┘  └──────┬──────┘  │ holder of a  │
                     │                │         │ storage key  │
                     │                │         └──────┬───────┘
                     └────────┬───────┴────────────────┘
                              │
                  ┌───────────▼────────────┐        ┌──────────────────┐
                  │  PostgreSQL 17         │◄───────┤ services/ingest  │
                  │  + pgvector (HNSW)     │        │ nightly Class B  │
                  │                        │        │ sync + quota     │
                  │  videos, chunks,       │        └──────────────────┘
                  │  watch_events,         │        ┌──────────────────┐
                  │  chapters, summaries   │◄───────┤ services/pipeline│
                  └───────────┬────────────┘        │ transcode → ASR  │
                              │                     │ → chunk → embed  │
                  ┌───────────▼────────────┐        │ → chapters       │
                  │ services/eval          │        └────────┬─────────┘
                  │ services/recsys        │                 │ holds no
                  └────────────────────────┘                 │ storage key;
                                                             │ asks media
                                                             ▼ to sign
                                                    Backblaze B2 (private)
```

`eval` and `recsys` are offline and read the same tables.

The boundaries are load-bearing rather than decorative. When AI playlists needed
to be saved as playlists owned by a real person, composition stayed in the AI
service and the write went to the core API, which already knew how to authorise
one. The AI service still has no concept of a user.

Full reasoning, including what the split costs:
[`docs/architecture.md`](docs/architecture.md).

## What is built

| Area | State |
|---|---|
| Database schema | All §6 entities, 13 migrations, 24 constraint assertions passing |
| Catalogue | 3,048 referenced talks across 37 channels, 17 owned |
| Ingest worker | Nightly sync, quota ledger, fails closed, idempotent |
| Pipeline | Stage machine, normalise, chunk, embed, chapter detection |
| AI layer | Semantic search, ask-video with refusal, summaries with timestamps |
| Evaluation | Harness, tested metrics, golden set — **no benchmark yet, deliberately** |
| Shorts | Vertical snap feed, window policy tested — **playback unverified** |
| Recommendations | Two-stage model, offline eval — **loses to popularity, analysed** |
| AI playlists | Brief → ordered playlist with a written rationale and per-item start times |
| Notifications | Trigger fan-out on publish and reply, idempotent, unread badge |
| Audio mode | Persistent bar, queue, shuffle/repeat, radio, time-synced transcript |
| Design system | Six tokens, two independently designed themes, visible at `/system` |
| Player | Adaptive HLS, chapter-segmented scrubber, §9.1 keyboard, resume |
| Player abstraction | Seek/play/pause/time store, verified against a real stream |
| Progress + resume | Append-only writes with JWT auth; endpoints tested against Postgres |
| Media storage | S3-compatible (Backblaze B2), hand-written SigV4, private bucket — **verified against live storage** |
| Upload | Browser → presigned PUT straight to the bucket, progress, cancel — **verified end to end** |
| Transcoding | ffmpeg → HLS ladder, never upscales, offers the source height — **verified on real files** |
| Channel ownership | One channel per person, created on first upload; uploads land private |
| Bunny path | Signing and webhook written and tested — **provider calls still unverified** |
| Auth | Sign-in, sign-up and session refresh, **verified end to end in a browser** |
| Core API | FastAPI, health, pipeline dashboard, watch events, resume, collections |
| CI | Nine jobs: web, API, AI, eval, recsys, media, ingest, pipeline, schema |
| Deployed | Live at [loupe-pied.vercel.app](https://loupe-pied.vercel.app) — three services on Render, Supabase, Backblaze B2, **£0/month** |

Test counts: 150 web, 122 API, 72 AI, 70 pipeline, 43 recsys, 41 media, 40 eval,
19 ingest, 15 auth, 24 schema assertions. **572 in total**.

Seed a browsable catalogue locally with:

```bash
psql "$DATABASE_URL" -f db/seed/0001_demo_catalogue.sql
```

That gives 9 owned talks (6 indexed, 3 mid-pipeline) and 48 referenced ones —
roughly the §4.1 shape of a real platform with an indexing backlog.

## Owning the media

For most of this project the catalogue pointed at somebody else's test stream.
Every talk shared one URL, every duration was a seeded guess, and `upload`
answered 503 because no media provider had ever been provisioned. The pipeline
that was supposed to process video had never processed any.

That is now closed. A file uploaded in the browser goes straight to a private
bucket, is transcoded into an HLS ladder, transcribed, chunked, embedded and
indexed, and plays back through the platform's own media service.

```
browser ──presigned PUT──► Backblaze B2 (private)
                                  │
                          transcoder (ffmpeg)
                                  │  reads source, writes renditions
                                  ▼
                    videos/<id>/hls/{master,360p/…}.m3u8
                                  │
browser ──► media service ──signs each playlist on request──► B2
                 │                        segments fetched direct
                 └── the only holder of storage credentials
```

**The bucket is private, and that turned out to be the better design.** It was
forced — Backblaze gates public buckets behind payment history — but a public
bucket hands out URLs that work forever, which means a takedown has to delete
the object because nothing else can revoke access. Signed, expiring URLs give
that back. It also kills a bug class this project had already hit: a permanent
URL cached in `localStorage` is exactly what broke playback once.

**Signing is written out rather than imported.** boto3 pulls roughly 50 MB to
produce a query string, and a SigV4 signature is a pure function of its inputs,
so it can be pinned to a fixed timestamp and anchored on a known value. It was
verified against live storage including a key containing a space, a plus and an
ampersand, which is the case that separates a signer that works from one that
works on easy input.

**The transcoder holds no storage credentials.** It asks the media service to
sign each URL through a token-gated endpoint, which is the only arrangement
that keeps "sole holder of provider credentials" true. Copying the keys into a
second service would have made that claim false.

**The ladder never upscales, and always offers the source height.** Both rules
fail silently. A 480p talk encoded at 720p is a bigger file that looks
identical; and a fixed 360/540/720 ladder gives a 480p source only its 360p
rung, so the talk plays *worse than the file that was uploaded* and nothing
reports a problem.

It runs on free infrastructure and the constraint is real rather than
decorative — see [Cost](#cost) and [Limitations](#limitations).

## Running it

One command, no hosted services, sign-in included:

```bash
createdb loupe_dev
DATABASE_URL=postgres://localhost:5432/loupe_dev ./db/migrate.sh
psql postgres://localhost:5432/loupe_dev -f db/seed/0001_demo_catalogue.sql
(cd web && pnpm install)
./dev.sh
```

That starts the web app, the API, the AI service and a development identity
provider, and prints a URL. `./dev.sh --stop` stops them.

Needs Node 22+, pnpm, Python 3.11+, uv, and Postgres 17 with pgvector. Full
walkthrough, including indexing the transcripts and swapping in a real Supabase
project: [`docs/running.md`](docs/running.md).

## Deploying it

All of it is deployed and working: the web app on Vercel, three services on
Render, Postgres on Supabase, media in Backblaze B2. Sign in, browse, watch a
talk the platform transcoded itself, and ask it a question.

`render.yaml` is a Blueprint covering the API, the AI service and the media
service. The two batch jobs — nightly ingest and the pipeline — run from
`.github/workflows/scheduled.yml` instead, because Render has no free plan for
cron jobs and both are batches that start, work and exit rather than the
long-running processes §14 put on Render.

Step-by-step, with what each step unblocks and the free-tier behaviours that
otherwise look like bugs: [`docs/deploying.md`](docs/deploying.md).

Five accounts are needed and none can be created on your behalf: Supabase
(database and auth in one free tier), Render, Vercel, Backblaze B2 for storage,
and Groq for transcription. All are free tiers; two of them want a card on file
without charging it, which is worth knowing before starting.

The single most likely thing to be wrong after a first deploy is `CORS_ORIGINS`.
Missing CORS is how comments, likes, saves and progress writes shipped broken
for four phases with every server-side test passing, and the symptom is a
browser console full of preflight failures while `curl` works perfectly.

Two more, both learned the slow way:

- **A pasted value can be wrong by one character and look present.** An
  `S3_ENDPOINT` ending `backblazeb2.co` instead of `.com` produced a bare 500
  on every playlist while every configuration check reported the variable set.
  `/health` on the media service now names any missing variable, and a failed
  bucket fetch returns 502 with the reason rather than 500 with none.
- **A database password containing `@` must be percent-encoded.** Otherwise the
  URL splits at the wrong place and Postgres reports a username that does not
  exist, which sends you looking in entirely the wrong direction. `db/url.sh`
  does the encoding without echoing anything.

## Repository layout

```
web/              Next.js app — all UI, routing, session
services/api/     FastAPI core API — CRUD, feed assembly, search orchestration
services/media/   Upload tickets, S3 signing, playlist rewriting for a private
                  bucket — the only holder of storage credentials
services/ingest/  Nightly referenced-content sync, quota accounting
services/pipeline/ Transcoding, transcription, chunking, embedding, chapters
services/ai/      Summarising, ask-video, semantic search, playlist composition
                  — the only service that holds a model key or a prompt
services/auth/    Development-only identity provider. Refuses to start outside
                  ENVIRONMENT=local. See ADR 0004
services/eval/    Golden set, metrics, and the evaluation runner
services/recsys/  Personas, candidate generation, ranking, offline evaluation
db/               SQL migrations, constraint tests, migration runner,
                  url.sh for building a connection URL, setup-hosted.sh for
                  preparing a hosted database, and seed/corpus/ — eight talks
                  rendered to speech, the only real audio this project has
dev.sh            Starts everything locally
render.yaml       Render Blueprint for the three web services
docs/             Plan, architecture writeup, decisions, ADRs, evaluation
```

The §5 service boundaries hold from Phase 0: the core API never holds storage
credentials and never calls an LLM, and the media service is the only thing
that has ever seen a storage key. A playback URL leaves it already signed, so
swapping providers touches one directory — which stopped being a claim and
became a fact when Backblaze replaced Bunny in an afternoon.

The transcoder tests that boundary hardest, because it needs to read and write
the bucket and holds no credentials for it. It asks the media service to sign
each URL instead. That costs a round trip and buys a real property: rotating the
storage key touches one service.

## Design

Red and white, with mainstream video-platform layout: a top bar with centred
search, an expanded sidebar carrying sections and subscribed channels, a dense
thumbnail grid. Both themes are designed to equal weight.

This reverses the plan's original position, which argued for an original visual
identity over a familiar feature set. That reversal is deliberate and recorded
in [ADR 0002](docs/adr/0002-visual-identity.md), along with what it costs and
the one thing it does not touch: no third-party trademark, logo, or brand colour
is reproduced. Loupe keeps its own wordmark.

The superseded direction is kept in
[`docs/design/direction.md`](docs/design/direction.md) rather than deleted, so
the decision reads as contested rather than assumed.

## Gate status

Reported per §18.1. Nothing here is rounded up.

| Phase | Gate | Status |
|---|---|---|
| 0 — Foundations | A logged-in user sees an empty shell on a public URL | **MET** — sign-in works end to end locally and on the deployed instance ([detail](#phase-0-detail)) |
| 1 — Media spine | One video plays adaptively with working seek and resume | **MET** — and beyond the gate: a file uploaded in the browser is transcoded, stored and played back from storage this project owns, verified on the deployed site |
| 2 — Core surfaces | A visitor can browse, watch, and comment | **MET** — all three verified in a browser, including a comment posted through the real API |
| 3 — Identity surfaces | All four built on the shared list abstraction, not four one-offs | **MET** — one `Collection` declaration each, one loader, one web component behind four routes. Likes, saves and subscriptions now verified writing through from the browser |
| 4 — Referenced ingest | 1,500+ Class B videos in the feed; unavailable states designed | **MET** — 3,048 across 37 channels, with designed unavailable states. From a fixture provider, not the real API |
| 5 — Pipeline | 50 hours indexed; stage machine survives forced failure injection | **PARTIAL** — failure injection met and tested; the transcode-to-index chain now runs on real files, but the corpus is far under 50 hours |
| 6 — AI layer | Citation-seek works end to end; refusal behaviour verified | **MET** — clicking a citation seeks the player; refusal verified by tests and by the eval harness, now against real transcripts. Citation *precision* is separately reported and is weak |
| 7 — Evaluation | Numbers and methodology in the README | **MET** — both below, including the sweep result that was deliberately not adopted |
| 8 — Shorts | No stutter on a mid-range Android device | **NOT MET** — no such device available, and the browser used for verification fires no scroll or IntersectionObserver events |
| 9 — Recsys | Beats popularity baseline, or the failure is analysed | **MET via the second clause** — it loses, and [`docs/recommendations.md`](docs/recommendations.md) is the analysis |
| 10 — Ship | Public URL, three-minute demo, architecture writeup | **PARTIAL** — URL and writeup done, now serving the platform's own media; the demo exists as a shot-by-shot script, because recording video is not something I can do |

Eight met, two partial, one not met. Both remaining partials need a corpus or
hardware rather than code, and each says which.

The design system is frozen as of Phase 2, per §18.3.

### Phase 0 detail

The gate is: *a logged-in user sees an empty shell on a public URL.*

**MET.**

| Clause | State |
|---|---|
| Public URL | **Met.** <https://loupe-pied.vercel.app> returns 200 on every route, and serves video from storage this project owns |
| Empty shell | **Met.** Both themes, all surfaces |
| Logged-in user | **Met.** Sign-up, sign-in, session refresh and a signed-in shell verified in a browser, locally against `services/auth` and on the deployed instance against Supabase |

This gate was partial for eleven phases because hosted auth needs an account
that cannot be created on somebody else's behalf. `services/auth`
([ADR 0004](docs/adr/0004-development-identity-provider.md)) exists precisely
so that five gates were not held hostage to that, and it did its job: when the
Supabase project arrived, the application code needed no changes, because it
had been speaking the same API all along.

Closing it also surfaced two things worth recording. The project signs tokens
with ES256 rather than the legacy HS256 secret, so verification had to handle
both — chosen by the token's own `alg`, with the two paths never sharing key
material. And a publishable key and a JWT secret look alike enough that the
wrong one was pasted into a `NEXT_PUBLIC_` variable once; the config now refuses
anything that is not a browser-safe key rather than shipping it to every
visitor.

### What signing in unblocked

Six things had been written and tested server-side and never once completed a
round trip from a browser. All six now have:

| | |
|---|---|
| Sign up, sign in, session refresh | **Verified** |
| Posting a comment | **Verified** — row in `comments` |
| Likes and saves | **Verified** — row in `saved_items` |
| Subscribing to a channel | **Verified** — row in `subscriptions` |
| Watch-progress writes | **Verified** — rows in `watch_events` |
| Composing an AI playlist | **Verified** — playlist with 8 items and per-item start times |
| Recording a download | **Verified** — 12,132,238 bytes, matching the CDN |

## Evaluation

**Still no benchmark. But the transcripts are real now, and the first thing
they did was expose a defect the fixture metrics had been hiding.**

Eight talks are spoken aloud and transcribed by whisper-large-v3-turbo. Against
a golden set of 36 cases, with questions written from the topics rather than by
reading the transcripts:

```
refusal accuracy    0.889      adversarial      8/8    was 4/8
false answer rate   0.000  ←   cross_video      4/4    was undefined
citation accuracy   0.421      out_of_scope     5/5
word error rate     0.048      factual        15/19
```

### The improvements are not fixes

The fixture run answered five of fourteen questions it should have refused. The
same threshold, unchanged, now refuses all thirteen. **Nothing about the
refusal logic changed.** The fixture corpus was one document repeated, so every
question retrieved something scoring highly and the threshold had no distance
to work with; six different talks give it some. The entire improvement is
attributable to data, and the same threshold over two thousand talks may be
wrong again in the other direction.

### The citation metric had been confirming a tautology

The fixture set scored **0.600** and, in its own words, read its expected
timestamps "from real chunk boundaries". A citation returned the chunk's start
time. So the metric was checking that a citation equals the chunk start, which
is true by construction.

Anchoring expected timestamps on the sentence that actually answers the
question dropped it to **0.053** — and the cause was not retrieval. §11.1
promises a citation lets you jump to *the moment*; what came back was the top of
a three-minute passage. The word-level timestamps needed to do better had been a
hard requirement since §10.2, and nothing had ever read them.

Fixed in two measured steps:

```
citing the chunk start                  0.053
+ sentence picked by word overlap       0.263
+ sentence picked by embedding          0.421
```

The middle step was not enough on its own, and the reason is the useful part:
nine of nineteen citations landed six to fourteen seconds out, which is one or
two sentences. Sentences inside one passage are all about the same subject and
differ by shades that shared vocabulary cannot capture.

**0.421 is not good.** A ±5s tolerance is roughly one sentence of speech, so a
citation that picks the sentence before the right one already fails. It is
reported because it is true and because it is eight times better than what the
0.600 was concealing.

### The threshold has inverted

The fixture run concluded it was too permissive. On real speech, 0.42 refuses
four answerable questions and 0.38 maximises accuracy. **0.42 is kept anyway**,
because §11.1 is explicit that a confident wrong answer is the failure that
matters, and 0.42 is the lowest threshold with none of them. That is a product
decision, not a metric to maximise.

### What this still is not

The speech is synthesised: no accents, no crosstalk, no room, no disfluencies,
no microphone at the back of a lecture theatre. Every one of those hurts, and
none is present. Some of the 4.8% word error rate is not error at all — the
scripts spell numbers out and the transcriber writes digits.

Eight talks is a small corpus, and precision over it is generous by
construction, which the talk about fooling yourself when evaluating retrieval —
itself in the corpus — says.

These are upper bounds. Full methodology, the threshold sweep, and what would
make this a benchmark: [`docs/evaluation.md`](docs/evaluation.md).

## Recommendations

**The model loses to a popularity baseline, and the failure is analysed rather
than tuned away.**

```
                     recall@20   NDCG@20
two-stage model        0.000      0.000
popularity baseline    0.020      0.019
```

Four causes, in order: the task is close to impossible as constructed (3,065
videos, ~8 held-out items, 20 slots — random scores 0.005); the persona
generator is stochastic, so even a perfect model cannot know which items were
drawn; stage-one candidate generation reaches only 18% of the targets because
3,000 of 3,065 catalogue rows are fixture-generated with identical
descriptions; and 818 training rows from five users is very little to learn
from.

The diversity penalty was the obvious suspect and an ablation ruled it out.

The model does personalise weakly — 3.3% of its top-20 comes from each
persona's preferred channels against 0.0% for the baseline — so the features
carry some signal and the pipeline is wired correctly.

**A win here would not have meant the recommendations are good.** Personas pick
by rules; a model trained on their output learns those rules. §12.2 forbids
presenting synthetic results as real, and the same applies to a synthetic-data
score. Full analysis: [`docs/recommendations.md`](docs/recommendations.md).

## AI playlists

Describe what you want to understand. Loupe searches inside the talks rather
than their titles, keeps the ones that genuinely address the brief, orders them,
and saves a real playlist with a written rationale and a start time per item.

The contract clause that shaped the design is the failure one: *return fewer
items rather than padding with poor matches.* A brief that clears the floor for
four talks produces four. A brief that clears it for none refuses.

Building it found a real bug in my own reasoning. The inclusion floor started as
the citation threshold, 0.34, on the assumption that "related enough to cite"
and "related enough to include" are the same question. Composing against the
real index:

```
how attention scales with sequence length    0.644 – 0.649
making inference cheap enough to deploy      0.493 – 0.505
underwater basket weaving for beginners      0.363 – 0.372   ← cleared 0.34
```

The third produced a confident eight-talk playlist of GPU systems talks. bge-m3
puts unrelated text near 0.35, so any absolute threshold down there sits inside
the model's noise floor and separates nothing.

The second finding matters more and raising the floor did not touch it. Look at
the on-topic range: eight talks separated by five thousandths, because all eight
indexed transcripts come from one fixture template. The ordering the rationale
describes is real in the code and meaningless in the output.

Both findings: [`docs/ai-playlists.md`](docs/ai-playlists.md).

## Cost

§14 sets a target of under $10 a month. Actual spend is **$0** — and it is no
longer $0 because nothing is provisioned. The platform stores, transcodes,
transcribes and serves real video on free tiers, deployed and running.

| Item | Actual | On what |
|---|---|---|
| Object storage and delivery | $0 | Backblaze B2 — 10 GB free, egress free up to 3× stored bytes. Currently 66 MB |
| Transcoding | $0 | ffmpeg, run wherever the poller runs. No managed encoder |
| Transcription | $0 | Groq free tier, whisper-large-v3-turbo with word timings |
| Database | $0 | Supabase free tier, Postgres 17 with pgvector |
| Three API services | $0 | Render free tier — which is why the embedder is a stand-in |
| Web hosting | $0 | Vercel Hobby. Non-commercial, so taking money means leaving it |
| Embeddings | $0 | bge-m3 locally; a hashing fallback in production |
| Domain | $0 | `loupe.video` looks unregistered. Not confirmed, not bought |

Every one of those has a wall, and knowing which wall comes first is the
engineering:

- **Storage is not the limit; attention is.** B2 gives free egress up to three
  times stored bytes, so 10 GB held is about 30 GB a month — roughly eighty
  complete views of a forty-minute talk. Past that it is $0.01/GB, which is
  cheap and predictable rather than free.
- **Memory is the limit on retrieval quality.** 512 MB cannot hold bge-m3, so
  production runs lexically. Fixing that costs money before anything else does.
- **Free tiers are somebody else's decision.** Oracle halved its always-free
  compute allocation mid-project without announcing it. That is the argument for
  the provider boundary in `services/media`, not a hypothetical one.

## What I would do next

In order, because the order matters more than the list.

**1. Get fifty hours of genuinely different talks.** The pipeline works — it
transcodes, transcribes, chunks, embeds and serves real video end to end. What
it has been given is eight synthesised talks. Chapter detection finding no
boundaries, the recommender losing to popularity, and playlist ranking becoming
noise are three separate writeups that all end at this same wall. Nothing else
on this list improves a quality number until it is done.

**2. Move the embedder somewhere with memory.** Production retrieves lexically
because bge-m3 does not fit in 512 MB, so the live site behaves materially worse
than the evaluation describes. This is the first thing worth spending money on,
and it is a small amount of money.

**3. Fix citation precision properly.** 0.421 within ±5s is eight times better
than citing the chunk start and still not good. The remaining errors are a wrong
sentence rather than a wrong passage, which is a narrower and more tractable
problem than it was a week ago.

**4. Put something in front of production.** There is no tracing, no error
reporting, no alerting and no rate limiting. Five real bugs were found this week
by a person clicking around; at any volume they would have been found by users,
silently. The one that mattered most produced no server-side symptom at all.

**5. Test shorts on real hardware.** The Phase 8 gate is the only one with no
partial credit, and it needs a mid-range Android phone rather than more code.

**6. Recruit fifteen to twenty real users for two weeks.** §12.2's third option.
The recommendation analysis says plainly that a win on synthetic data would not
have meant the recommendations are good.

Deliberately not on this list: tuning any threshold to improve a published
number, and adding features. The gap between this project and a convincing one
is now about the corpus and about production discipline, not about credentials —
those are provisioned and working.

## Limitations

Recorded as they are incurred, per the working agreement.

- **English only.** The evaluation set will have four categories rather than the
  five originally specified; the non-English category is dropped, and with it
  the cross-language retrieval demonstration.
- **Recommendations will be trained on synthetic histories.** Disclosed in the
  data itself via `watch_events.is_synthetic`, not only in prose.
- **`loupe.video` is unverified.** DNS suggests it is unregistered. Not confirmed
  at a registrar, and not purchased.
- **Bunny integration is written but never executed.** Superseded rather than
  fixed: storage is now S3-compatible and verified against live Backblaze B2,
  and the Bunny adapter remains beside it, still unexercised. It stays because
  [ADR 0001](docs/adr/0001-media-provider.md) chose it and nothing disproved
  that choice — it was never provisioned, which is a different thing.

- **Production retrieval runs on a hashing fallback, not a real embedding
  model.** bge-m3 needs roughly 2 GB with torch; a free Render instance has
  512 MB. So the deployed services embed with a hashing stand-in, and retrieval
  there is lexical rather than semantic: near-verbatim questions are answered,
  paraphrases are usually refused, and playlist composition mostly declines.
  Locally, with the real model, the same corpus behaves as the evaluation
  describes. This is the cost of £0 and the first thing worth money.

- **Free instances spin down.** The first request after a quiet period can take
  fifty seconds, and on a video that is indistinguishable from a broken player.

- **The corpus is synthesised speech.** Real audio, real recognition, real
  timings — and clean in every way a conference recording is not. See
  [Evaluation](#evaluation).

- **Citations land within ±5s on 42% of answered questions.** Better than the
  chunk-start behaviour it replaced by eight times, and not good. The remaining
  errors are a wrong sentence rather than a wrong passage.
- **Progress writes have not run end to end.** The endpoints are tested against
  a real Postgres and the throttling logic is tested in isolation. Sign-in now
  works in a browser, so this is testable and has not been tested.
- **The shorts feed has never been seen playing.** The window policy §13
  specifies — active plus two ahead loading, destroy beyond ±3 — is proven by
  16 unit tests, and the API and layout are verified. But the browser available
  for verification fires no scroll events and no IntersectionObserver
  callbacks, so scroll-driven activation could not be exercised at all, and the
  gate ("no stutter on a mid-range Android") needs hardware this project does
  not have. Both are open.
- **Shorts media is 16:9, not vertical.** The feed is built for 9:16 and the
  player crops to fill, which is what a real client does with mismatched
  aspect — but these are not genuinely vertical videos.
- **Comment posting has never completed.** The endpoint is tested against a real
  Postgres including the one-reply-level limit, but the browser path needs a
  signed-in session, which needs Supabase.
- **Search covers two different things at once.** Semantic search runs over
  transcript chunks for Class A; Class B can only ever support title,
  description, and channel matching. Results from the two are not comparable
  measurements, and although the UI marks which is which, the ranking still
  mixes them.
- **Most transcripts are still generated.** Eight talks carry real recognition
  output, stored with `engine = 'groq-whisper'`. The rest of the seeded
  catalogue still points at a reference stream and carries fixture text stored
  with `engine = 'fixture'` — both are identifiable with one query, which is
  why the distinction can be stated precisely rather than approximately.
- **Answers are extractive, not generated.** With no model key configured, an
  answer is the retrieved transcript passages themselves. That cannot state
  anything the speaker did not say, which makes it a defensible baseline rather
  than a degraded mode — and the right thing for §11.2 to measure a generative
  answerer against. Setting `GEMINI_API_KEY` routes to a model behind the same
  interface, with the refusal check still made before it is called.
- **Well under 50 hours indexed.** The Phase 5 gate asks for 50. The pipeline
  that would get there now works on real files end to end; what is missing is
  fifty hours of talks to put through it, not the machinery.
- **The AI playlist inclusion floor is calibrated on three briefs.** It
  separates on-topic from off-topic on this corpus and is recorded as
  provisional rather than tuned, because three observations over eight videos is
  not a calibration.
- **The demo video does not exist as a video.** §16 asks for three minutes of
  screen recording. What exists is a shot-by-shot script with the seed state
  each shot needs, in [`docs/demo-script.md`](docs/demo-script.md), because
  recording and narrating video is outside what I can produce.
- **The referenced catalogue is generated, not ingested.** No YouTube Data API
  key is configured, so the worker runs against a deterministic fixture
  provider. The worker, the quota ledger, the idempotency, and the write path
  are all real and tested; only the upstream is not. Set `YOUTUBE_API_KEY` and
  the same code walks real channels.
- **Thumbnails are stock photographs, not frames from the talks.** They are
  keyed to the talk id so each talk always shows the same image, but they have
  nothing to do with its content. Real frames arrive when the media provider
  generates sprite sheets.
- **Background audio on iOS will not work.** Safari suspends web audio once the
  browser is backgrounded. Media Session delivers the lock-screen controls and
  metadata but not the background execution, and §3.2 rules out a native app, so
  a PWA is the ceiling. Audio does continue during in-app navigation.
- **Media Session is unverified.** Lock-screen controls and hardware media keys
  need a phone.
- **Every fixture episode shares one media URL.** Downloads are cached by media
  URL, so downloading one demo episode makes all six report as downloaded. That
  is accurate — the same bytes really would play for any of them — and it
  disappears the moment episodes have distinct URLs, which they do anywhere but
  the fixture.
- **Playing a downloaded episode with the network genuinely down is
  unverified.** The download, the cache contents, and the service worker's
  offline serving and range slicing are each verified in a browser — the last
  two against an unreachable host, which is the only way to make the network
  branch fail on demand. Putting a real device in aeroplane mode is not.
- **Performance targets are unmeasured.** LCP under 2.5s and player
  time-to-first-frame under 1.5s need a deployed API to test against.

## Audio mode

Spoken audio with the controls of a music app: a bar that survives navigation, a
queue with shuffle and repeat, radio from an episode, playback speed, a sleep
timer, OS media controls, and a transcript that follows the audio and seeks when
you click a line.

Spoken audio rather than music, deliberately. Real music needs licensing this
project does not have, and CC catalogues are overwhelmingly instrumental — so
the semantic layer, the entire differentiator, would do nothing. Spoken audio
inverts that: every capability already built applies unchanged.

**One column, not a second schema.** `content_kind` on `videos`. Eight of the
nine surfaces audio mode needs required no schema change, so the comments
component, the AI panel, and the channel page appear on an episode page
untouched.

**The week-one abstraction paid for itself here.** §5.1 asked for a
framework-free player store before anything consumed it. Moving the media
element out of the video page and into the root layout took one line, and
nothing that reads playback state changed, because none of it ever knew where
the element lived.

**Two things were built and then rebuilt.** The queue started as React state,
which was wrong — a queue restored from storage is external state, and it is now
a plain store behind `useSyncExternalStore`. And the transcript view used
retrieval chunks, which put three and a half minutes of speech on one line;
rebuilt on word timings, the same episode went from 13 walls of text to 340
readable lines.

**The player bar expands to a full-screen view** where the transcript is the
hero rather than a placeholder square — a music app fills that space with
artwork, and an episode has none. It shares the bar's media element, so
expanding never interrupts playback.

**The sleep timer counts down in seconds** and is computed from a deadline
rather than decremented, so a backgrounded tab that only gets one timer callback
a minute still stops the audio on time.

**The playhead survives a reload.** Saved per episode, restored on load, and
declined when the episode was effectively finished — the same two §9.1
thresholds the API applies, so the two paths cannot resume the same episode to
different places.

**Offline downloads store audio only.** 12MB per episode against 27MB for the
smallest video rendition, which is the right trade for a podcast. A rewritten
master playlist offers just the audio track, so an offline player cannot pick a
rendition that was never stored, and the service worker slices HLS byte ranges
out of the cached file and returns them as proper 206s. Downloads are limited to
Class A by a database trigger, because ADR 0003's rule is about what Loupe owns
and the schema can enforce exactly that.

Full account, including what is verified and what needs a phone:
[`docs/audio-mode.md`](docs/audio-mode.md).

## Out of scope

Deliberate exclusions, not omissions: content moderation and trust & safety,
monetisation, live streaming, native mobile apps, multi-tenant creator
analytics, and video-native (non-transcript) visual retrieval.
