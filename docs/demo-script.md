# Three-minute demo

Plan ref: §16. *Upload → processing → watching → asking a question → clicking a
citation → semantic search finding a moment. Show the product, not the codebase.*

**This is a script, not a recording.** Producing screen capture and narration is
outside what I can do, so what follows is every shot, its timing, what to say
over it, and the state the database has to be in first. Someone with a screen
recorder and three minutes can shoot it as written.

Two things in it need credentials that do not exist yet, and both have a
documented substitute below rather than being quietly cut.

---

## Before recording

```bash
# 1. Schema and catalogue
createdb loupe_demo
DATABASE_URL=postgres://localhost:5432/loupe_demo ./db/migrate.sh
psql "$DATABASE_URL" -f db/seed/0001_demo_catalogue.sql
psql "$DATABASE_URL" -f db/seed/0002_shorts.sql

# 2. Index the owned talks so the AI surfaces have something to work with
cd services/pipeline && DATABASE_URL=... uv run python -m app.run --all

# 3. Services
cd services/api && DATABASE_URL=... uv run uvicorn app.main:app --port 8010
cd services/ai  && DATABASE_URL=... USE_REAL_EMBEDDINGS=true \
                   uv run uvicorn app.main:app --port 8031
cd web && pnpm dev
```

Set the theme to dark before shot 1 and leave it. Toggling mid-demo costs four
seconds and shows nothing that a still frame would not.

Sign in first. Three of the seven shots need a session.

---

## Shot 1 — the feed (0:00 to 0:18)

**Screen.** `/` on a 1440px viewport. Scroll one page slowly, then stop.

**Say.** "Loupe is a video platform for machine learning talks. Three thousand
talks in the feed. Seventeen of them are fully indexed, and the difference
between those two numbers is the whole architecture."

**Why it opens here.** The feed has to look like a product before any claim
about the intelligence layer is worth making. §4.1 is the argument and this shot
is the argument's evidence.

## Shot 2 — the capability difference (0:18 to 0:40)

**Screen.** Click a referenced talk. Point at the unavailable state on the AI
panel. Go back, click an owned talk, and let the AI panel render with its
summary and chapters.

**Say.** "This one is referenced. Metadata only, no transcript, so there is
nothing to ask questions about, and the page says so instead of showing a
disabled button. This one is owned. Word-level transcript, chunked, embedded."

**Why.** This is the single most consequential design decision in the project
and it is visible in eight seconds. Most people watching will have seen products
that fake this and they will recognise what is being shown.

## Shot 3 — playback and the scrubber (0:40 to 1:00)

**Screen.** Press play. Let it run four seconds. Hover the scrubber to show the
chapter segments. Press `J`, then `L`, then `K`.

**Say.** "Custom player, adaptive HLS. The scrubber is segmented by chapters
that were detected from embedding drift, not from anything the uploader typed.
Keyboard controls are the ones you already know."

**Note.** The demo stream has no speech in it, so keep this shot short and do
not draw attention to the audio.

## Shot 4 — ask the video (1:00 to 1:35)

**Screen.** In the AI panel, type: *what makes attention expensive at long
sequence lengths?* Wait for the answer with its citations.

**Say.** "Ask it something. The answer comes back with citations, and each one
is a timestamp."

**Then** ask: *what does the speaker say about the 2008 financial crisis?*

**Say.** "And when the talk does not cover something, it says so instead of
producing something plausible. That refusal is a threshold on retrieval score,
decided before anything is generated. Refusal rate is a metric we publish, not a
bug we hide."

**Why this is the centre of the demo.** §11.1 calls a confident wrong answer the
failure mode that gets noticed in a demo. Showing the refusal on purpose is the
strongest thirty seconds available.

## Shot 5 — the citation seeks (1:35 to 1:50)

**Screen.** Scroll back to the first answer. Click a citation. The player jumps
and plays from that second.

**Say.** "Clicking a citation seeks the player. That is the reason the ASR has
to produce word-level timestamps. If this lands in the wrong place, nothing else
in the intelligence layer is believable."

**Do not rush this shot.** It is the one that makes the product legible, and it
is over in three seconds if you let it be.

## Shot 6 — search inside the talks (1:50 to 2:20)

**Screen.** Search for *memory bandwidth is the real constraint*. Results show
ranked talks, each with the matching moment and its timestamp. Click one
moment.

**Say.** "Search runs over transcript chunks, so this is not matching titles. It
found the moment inside a talk and it will open there."

## Shot 7 — compose a playlist (2:20 to 2:50)

**Screen.** `/playlists`. Type *how attention scales with sequence length* and
press Compose. The playlist opens with its rationale and per-item start times.

**Say.** "Give it a brief and it composes a playlist by searching inside the
talks. Each item opens at the moment that addresses the brief, and the rationale
explains the ordering it actually used."

**Then** compose *underwater basket weaving for beginners* and let it refuse.

**Say.** "Same refusal behaviour. Nothing in the catalogue covers that, so it
says so rather than returning eight talks that vaguely rhyme with the words."

## Shot 8 — close (2:50 to 3:00)

**Screen.** Back to the feed. Hold still.

**Say.** "Two content classes, a resumable processing pipeline, a semantic layer
that refuses when it should, and a set of evaluation numbers that includes the
ones that came out badly. Everything is in the README."

**Do not** end on a promise about what is coming next. The honest numbers are a
stronger close than a roadmap.

---

## The two shots that need credentials

§16 asks for **upload → processing** at the start. Both are written, tested, and
have never run against a real provider.

**Substitute, if credentials are still missing:** open `/system` and show the
pipeline dashboard with counts per stage, then say: "Uploads go to Bunny, which
webhooks back when transcoding finishes and the video enters this machine. The
signing and webhook handling are tested against independently computed vectors.
The provider account is not provisioned, so I am showing you the state machine
rather than claiming a round-trip that has not happened."

That sentence is worth more than a faked upload. Anyone senior enough to be
watching has seen a demo that quietly skipped the part that does not work.

**To shoot it properly**, provision Bunny and add `BUNNY_*` to
`services/media/.env`. The upload page at `/upload` is already built.

## Things to keep out

- The code. §16 says show the product, and every second on an editor is a second
  not spent on the thing the product does.
- The theme toggle. It is nice and it is not what this is about.
- Shorts. The feed is built but has never been seen playing on real hardware,
  and demoing something unverified is exactly the habit the rest of this project
  is arguing against.
- Any sentence beginning "and of course you could imagine".
