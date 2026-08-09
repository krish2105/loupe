# Loupe

**A video platform for AI and machine learning talks, with a semantic layer.**

Search *inside* a talk, ask it questions and get answers that cite the exact
moment, and land on that moment with one click. Built on an owned catalogue,
because transcripts are what every interesting feature here depends on.

> **Status: Phase 0 of 11.** Foundations only. There is no video playback, no
> catalogue, and no AI layer yet. What exists is the schema, the design system,
> the player abstraction, auth, and CI. See [gate status](#phase-0-gate-status).

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

## What is built

| Area | State |
|---|---|
| Database schema | All §6 entities, 7 migrations, 19 constraint assertions passing |
| Design system | Six tokens, two independently designed themes, visible at `/system` |
| Player | Adaptive HLS, chapter-segmented scrubber, §9.1 keyboard, resume |
| Player abstraction | Seek/play/pause/time store, verified against a real stream |
| Progress + resume | Append-only writes with JWT auth; endpoints tested against Postgres |
| Media service | Bunny upload signing, webhook, signed playback URLs — **provider calls unverified** |
| Auth | Supabase Auth wired; **unverified — needs provisioning** |
| Core API | FastAPI, health, pipeline stages, watch events, resume |
| CI | Web, API, media, and schema jobs |
| Staging deploy | Live at [web-jade-two-b023n56l0y.vercel.app](https://web-jade-two-b023n56l0y.vercel.app) |

Test counts: 22 web, 14 API, 12 media, 19 schema assertions.

## Running it

Requires Node 22+, pnpm, Python 3.11+, uv, and Postgres 17 with pgvector.

```bash
brew install postgresql@17 pgvector && brew services start postgresql@17
createdb loupe_dev
DATABASE_URL=postgres://localhost:5432/loupe_dev ./db/migrate.sh
```

```bash
cd web && pnpm install && pnpm dev
```

Visit `/system` to see the design tokens in both themes. Copy `.env.example` and
fill in the Supabase keys to enable sign-in.

## Repository layout

```
web/              Next.js app — all UI, routing, session
services/api/     FastAPI core API — CRUD, feed assembly, search orchestration
services/media/   Upload signing, provider webhooks, playback URL signing
db/               SQL migrations, constraint tests, migration runner
docs/             Plan, decisions, ADRs, design direction
```

The §5 service boundaries hold from Phase 0: the core API never holds media
provider credentials and never calls an LLM, and the media service is the only
thing that has ever seen a Bunny key. A playback URL leaves that service already
signed, so swapping providers touches one directory.

## Design

Dark-first, with a light theme designed independently rather than inverted —
dark's referent is a dimmed auditorium, light's is a lit surface, and they are
deliberately opposite in temperature.

One system rule does most of the work: **chrome is achromatic, and colour means
the machine found something.** Buttons, links, navigation, and focus rings are
built entirely from neutrals. The single accent appears only on the semantic
layer — transcript matches, citation marks, the AI-ready state.

Full direction in [`docs/design/direction.md`](docs/design/direction.md).

## Phase 0 gate status

The gate is: *a logged-in user sees an empty shell on a public URL.*

**PARTIAL — two of three clauses met.**

| Clause | State |
|---|---|
| Public URL | **Met.** <https://web-jade-two-b023n56l0y.vercel.app> returns 200 on `/`, `/login`, and `/system` |
| Empty shell | **Met.** Rail, search capsule, empty state, both themes |
| Logged-in user | **Not met.** No Supabase project, so no sign-in has ever succeeded |

The auth code path is complete and builds, but complete is not the same as
verified, and nothing here should claim a round-trip that has not happened.
Local development runs against Homebrew Postgres because this machine has no
Docker, which rules out `supabase start`.

**To close it** (about ten minutes):

1. Create a free Supabase project.
2. Put `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in
   `web/.env.local`, and add both to the Vercel project's environment.
3. Apply the schema to it:
   ```bash
   DATABASE_URL="<supabase pooler url>" ./db/migrate.sh
   psql "$DATABASE_URL" -f db/migrations/supabase/0001_auth_link.sql
   ```
4. Redeploy, sign up, and confirm the shell renders with the account control
   showing the signed-in initial.

## Limitations

Recorded as they are incurred, per the working agreement.

- **English only.** The evaluation set will have four categories rather than the
  five originally specified; the non-English category is dropped, and with it
  the cross-language retrieval demonstration.
- **Recommendations will be trained on synthetic histories.** Disclosed in the
  data itself via `watch_events.is_synthetic`, not only in prose.
- **`loupe.video` is unverified.** DNS suggests it is unregistered. Not confirmed
  at a registrar, and not purchased.
- **Bunny integration is written but never executed.** The signing functions are
  tested against independently computed vectors, because a wrong signature
  surfaces only as a CDN 403 with no diagnostic. The API calls themselves have
  never run — no credentials exist yet.
- **Progress writes have not run end to end.** The endpoints are tested against
  a real Postgres and the throttling logic is tested in isolation, but the
  browser has never sent one, because that needs a signed-in session.
- **No staging deploy yet**, so the performance targets (LCP under 2.5s, player
  time-to-first-frame under 1.5s) are unmeasured.

## Out of scope

Deliberate exclusions, not omissions: content moderation and trust & safety,
monetisation, live streaming, native mobile apps, multi-tenant creator
analytics, and video-native (non-transcript) visual retrieval.
