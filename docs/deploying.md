# Deploying Loupe

Plan ref: §14. Vercel for the web app, Render for the API and workers, Supabase
Postgres for the database, Bunny Stream for media. Target under $10 a month.

**Current state: the web app is deployed and nothing else is.**
<https://web-jade-two-b023n56l0y.vercel.app> serves the interface against no
API, which is why it browses and does not do anything. Everything below is the
path from that to a working deployment, and each step says what it unblocks.

Four accounts are needed and none of them can be created on your behalf:
Supabase, Render, Vercel (already connected), and optionally Bunny.

---

## 1. Database and auth — Supabase

One account covers both, which is the reason §14 chose it: the app needs
pgvector and it needs a GoTrue instance, and this is one free tier providing
both.

1. Create a project. Note the region — put Render in the same one.
2. Enable pgvector: **Database → Extensions → vector**.
3. Apply the schema, using the **pooler** connection string:

   ```bash
   DATABASE_URL="postgres://postgres.<ref>:<password>@<region>.pooler.supabase.com:6543/postgres" \
     ./db/migrate.sh

   psql "$DATABASE_URL" -f db/migrations/supabase/0001_auth_link.sql
   ```

   The second file is the hosted-only foreign key from `users` to `auth.users`.
   It is separate because local development has no `auth` schema, and a
   migration that only runs in one environment should say so by being a
   different file.

4. Optionally seed a catalogue so the deployment is not empty:

   ```bash
   psql "$DATABASE_URL" -f db/seed/0001_demo_catalogue.sql
   psql "$DATABASE_URL" -f db/seed/0002_shorts.sql
   psql "$DATABASE_URL" -f db/seed/0003_audio.sql
   ```

Collect three values from **Project Settings → API**: the project URL, the anon
key, and the JWT secret.

**Do not deploy `services/auth`.** It is a development identity provider
([ADR 0004](adr/0004-development-identity-provider.md)) and refuses to start
unless `ENVIRONMENT=local`. Supabase Auth replaces it, and the swap is two
environment variables because it was built to speak the same API.

## 2. API and workers — Render

`render.yaml` at the repository root is a Blueprint covering all five: the core
API, the AI service, the media service, the nightly ingest cron and the pipeline
cron.

1. **New → Blueprint**, point it at the repository. Render reads `render.yaml`.
2. Fill in the prompted secrets. Every one is marked `sync: false`, which is
   Render's way of saying it must never live in the repository:

   | Variable | Services | Value |
   |---|---|---|
   | `DATABASE_URL` | all | Supabase **pooler** URL. The direct connection limit is small and free instances open a connection per cold start |
   | `SUPABASE_JWT_SECRET` | api | Supabase → Settings → API → JWT Secret |
   | `CORS_ORIGINS` | api, ai | The Vercel URL, exactly, with scheme and no trailing slash |
   | `AI_SERVICE_URL` | api | `https://loupe-ai.onrender.com`, once it exists |
   | `GEMINI_API_KEY` | ai | Optional — absent, answers stay extractive |
   | `BUNNY_*`, `WEBHOOK_SECRET` | media | Step 4, or leave empty and skip media |
   | `YOUTUBE_API_KEY` | ingest | Optional — absent, the fixture provider runs |

3. Deploy. `AI_SERVICE_URL` is a chicken-and-egg: deploy, take the AI service's
   URL, set it on the API, redeploy the API.

Two things about the free tier that will otherwise look like bugs:

**Instances sleep.** The first request after inactivity takes several seconds
while the container wakes. Fine for a portfolio, wrong for a demo — warm it
first, or pay for the always-on tier.

**The embedding model does not fit.** bge-m3 is around 2GB. `render.yaml` sets
`USE_REAL_EMBEDDINGS=false`, so retrieval falls back to the deterministic
embedder and semantic search degrades to keyword — which the API reports in its
`mode` field rather than hiding. Real semantic search needs a paid instance.

## 3. Web app — Vercel

Already connected. Add four environment variables under **Settings →
Environment Variables**, for Production and Preview:

```
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
NEXT_PUBLIC_API_URL=https://loupe-api.onrender.com
NEXT_PUBLIC_AI_URL=https://loupe-ai.onrender.com
```

Redeploy. Vercel bakes `NEXT_PUBLIC_*` into the build, so setting them without
redeploying changes nothing.

**Then set `CORS_ORIGINS` on Render to this exact origin.** Missing CORS is how
comments, likes, saves, subscriptions and progress writes shipped broken for
four phases with every server-side test passing. It is the single most likely
thing to be wrong after a first deploy, and the symptom is a browser console
full of preflight failures while `curl` works perfectly.

## 4. Media — Bunny Stream (optional)

Only needed for uploading. The seeded catalogue plays from a public reference
stream without it.

1. Create a Stream library. Note the library id and the pull zone.
2. From the library's API settings, take the API key and the token
   authentication key. They are different keys on purpose: one signs management
   calls, the other signs what the public fetches.
3. `openssl rand -hex 32` for `WEBHOOK_SECRET`. Bunny does not sign Stream
   webhooks, so the endpoint sits behind an unguessable path segment instead.
4. Point the library's webhook at
   `https://loupe-media.onrender.com/webhooks/bunny/<WEBHOOK_SECRET>`.

**None of this has ever run against the real provider.** The signing functions
are tested against independently computed vectors, because a wrong signature
surfaces only as a CDN 403 with no diagnostic. The API calls themselves are
unverified.

## 5. Transcription

`render.yaml` runs the pipeline every thirty minutes with `USE_REAL_MODELS=false`,
which produces fixture transcripts. Real transcription runs at roughly 1×
realtime on CPU and does not belong on a free web instance.

§10.3's approach: run the initial batch on free GPU compute (Colab, Kaggle),
export the transcripts as a portable artifact, and load them into the database.
The pipeline stays the scheduler for anything new.

The cost ceiling is enforced in the worker rather than by discipline —
`TRANSCRIPTION_MINUTES_CAP`, read before a job is claimed.

## What each step unblocks

| Step | What starts working |
|---|---|
| Supabase | Sign-in, and with it comments, history, playlists, subscriptions, downloads |
| Render API | The feed, video pages, search, every read the browser makes |
| Render AI | Summaries, ask-video, semantic search, AI playlists |
| Vercel variables | The browser reaching any of it |
| `CORS_ORIGINS` | Every browser write. Skip it and everything above looks broken |
| Bunny | Uploading, transcoding, signed playback |
| GPU batch | Real transcripts, and with them any evaluation number that means anything |

## Cost

| | Plan | |
|---|---|---|
| Vercel | Hobby | $0 |
| Render | Free × 5 | $0, with sleeping instances |
| Supabase | Free | $0, 500MB and 2 CPU-hours a week |
| Bunny Stream | Pay as you go | ~$4/month at this scale |
| Gemini | Free tier | $0, with a hard cap in the worker |

Under $10 as §14 requires, and $0 without media. The two numbers that move under
real use are media, which scales with storage plus egress and is why the owned
catalogue is capped at 50 hours, and transcription, which is one-time per video
and is the reason for a cap enforced in code.

## Verifying a deploy

```bash
curl https://loupe-api.onrender.com/health     # {"status":"ok","database":"ok"}
curl https://loupe-ai.onrender.com/health
curl https://loupe-api.onrender.com/v1/feed | head -c 200
```

Then in a browser: sign up, post a comment, and watch thirty seconds of a talk.
Those three exercise auth, a browser write through CORS, and the append-only
watch log. If all three work, the deployment is real — and if the comment fails
while `curl` succeeds, it is `CORS_ORIGINS`.
