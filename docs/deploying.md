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

## Finding the credentials

Two values do most of the work. Neither should ever be pasted into a chat, a
commit, or an issue — put them straight into the platform's secret store.

### DATABASE_URL

From Supabase, after creating the project in step 1.

1. Open the project and click **Connect** at the top of the dashboard. (Older
   dashboards put this under **Project Settings → Database → Connection
   string**. Supabase moves it; the value is the same.)
2. Choose **Transaction pooler** — the URI on port **6543**, host
   `aws-0-<region>.pooler.supabase.com`.
3. Copy the URI. It looks like:

   ```
   postgresql://postgres.abcdefghijklm:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
   ```

4. Replace `[YOUR-PASSWORD]` with the database password you set when creating
   the project. Forgotten it? **Project Settings → Database → Database password
   → Reset**. Resetting invalidates the old one everywhere, so update every
   place that holds it.
5. If the password contains `@ : / ? # [ ] %`, percent-encode it, or the URL
   parses wrongly and you get an authentication error that blames the username.

Test it before pasting it anywhere:

```bash
psql "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres" -c "SELECT 1"
```

**The IPv6 notice can be ignored.** The dialog warns that the transaction
pooler uses IPv6 by default and offers a paid IPv4 add-on. The *shared* pooler
host resolves to IPv4 as well — `aws-0-ap-southeast-2.pooler.supabase.com`
returns three A records and accepts connections on 6543 — so GitHub runners and
Render instances, which are IPv4-only, reach it without the add-on. Check for
yourself before paying for it:

```bash
dig +short aws-0-<region>.pooler.supabase.com A
```

Addresses in the output mean IPv4 works. The warning applies to the **direct**
connection, which genuinely is IPv6-only.

**Which pooler.** Transaction (6543) is right for both the Render web services
and the GitHub Actions jobs: it survives cold starts and short-lived connections,
which is what both are. Session pooler (5432) holds a real backend connection per
client and the free tier has few of them.

Every service in this repository opens its pool with `statement_cache_size=0`,
which the transaction pooler requires. PgBouncer in transaction mode hands a
connection to a different client between statements, and asyncpg's cached
prepared statements then collide with `prepared statement
"__asyncpg_stmt_1__" already exists` — an error that reads like a bug in this
code and is not. It is set unconditionally, because it is harmless on a direct
connection and a setting that only applies to one URL is a setting nobody
remembers.

**Where it goes:**

| | |
|---|---|
| Render | Prompted by the Blueprint, once per service |
| GitHub Actions | **Settings → Secrets and variables → Actions → New repository secret**, named `DATABASE_URL` |
| Locally | Not needed. `./dev.sh` uses your local Postgres |

Never in Vercel. The browser has no business holding a database URL, and
`NEXT_PUBLIC_` anything is shipped to it.

### YOUTUBE_API_KEY

Entirely optional. Without it the ingest worker runs against a deterministic
fixture provider, which is what the current 3,048-video catalogue came from. The
worker, the quota ledger, the idempotency and the write path are identical
either way; only the upstream differs.

1. Go to <https://console.cloud.google.com> and create a project, or pick one.
2. **APIs & Services → Library**, search **YouTube Data API v3**, press
   **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**. Copy it.
4. Press **Edit API key** and restrict it. An unrestricted key is a key anyone
   who finds it can spend:
   - **API restrictions → Restrict key → YouTube Data API v3**
   - Leave application restrictions as **None**. Referrer and IP restrictions
     are for browsers and fixed addresses; this key is used by a GitHub runner
     whose IP changes every run.
5. The default quota is 10,000 units a day. §4.2 caps this project at 2,000, so
   a runaway loop hits our ceiling before Google's.

**Where it goes:** the same GitHub Actions secrets page, named
`YOUTUBE_API_KEY`. Not Render — the ingest worker moved to Actions.

### The rest, briefly

| Secret | Where to find it |
|---|---|
| `SUPABASE_JWT_SECRET` | Supabase → **Project Settings → API → JWT Settings → JWT Secret** |
| `NEXT_PUBLIC_SUPABASE_URL` | Same page, **Project URL** |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Same page. Newer projects show `sb_publishable_…`; older ones call it **anon public** and `NEXT_PUBLIC_SUPABASE_ANON_KEY` works too. Safe in the browser. The **secret** key beside it — `sb_secret_…` or `service_role` — is not, and this project never uses one |
| `CORS_ORIGINS` | Your Vercel URL, exact, with scheme and no trailing slash |
| `GEMINI_API_KEY` | <https://aistudio.google.com/apikey>. Optional |
| `BUNNY_*` | Bunny dashboard → Stream → your library → **API** |
| `WEBHOOK_SECRET` | You generate it: `openssl rand -hex 32` |

---

## 1. Database and auth — Supabase

One account covers both, which is the reason §14 chose it: the app needs
pgvector and it needs a GoTrue instance, and this is one free tier providing
both.

1. Create a project. **Note the region.** Every API request makes several
   database round trips, so a service on the wrong continent pays that latency
   several times over on every page. `render.yaml` is set to `singapore`, which
   is the nearest Render region to `ap-southeast-2`; change it in all three
   services if your project is elsewhere. Render offers oregon, ohio, virginia,
   frankfurt and singapore.
2. Enable pgvector: **Database → Extensions → vector**.
3. Prepare the database in one command:

   ```bash
   ./db/setup-hosted.sh "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres" --seed
   ```

   It checks the connection, enables pgvector, applies every migration, applies
   the hosted-only link from `users` to `auth.users`, and with `--seed` loads a
   catalogue. It never prints the URL, because that contains a password and a
   terminal is a log.

   The auth link is a separate file rather than a migration in the chain because
   local development has no `auth` schema, and a migration that only runs in one
   environment should say so by being a different file.

   Quote the URL. Passwords contain characters the shell would otherwise
   interpret.

Collect three values from **Project Settings → API**: the project URL, the anon
key, and the JWT secret.

**Do not deploy `services/auth`.** It is a development identity provider
([ADR 0004](adr/0004-development-identity-provider.md)) and refuses to start
unless `ENVIRONMENT=local`. Supabase Auth replaces it, and the swap is two
environment variables because it was built to speak the same API.

## 2. API and workers — Render

`render.yaml` at the repository root is a Blueprint covering three web services:
the core API, the AI service and the media service.

The two batch jobs are not in it. **Render has no free plan for cron jobs** — a
Blueprint listing one is rejected with `free not a valid plan for service type
cron` — so the nightly ingest and the pipeline run from
`.github/workflows/scheduled.yml`, which is free on a public repository and
needs nothing but a `DATABASE_URL` secret. See [step 2b](#2b-the-batch-jobs).

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
   | `YOUTUBE_API_KEY` | — | Moved to GitHub Actions; see step 2b |

3. Deploy. `AI_SERVICE_URL` is a chicken-and-egg: deploy, take the AI service's
   URL, set it on the API, redeploy the API.

### 2b. The batch jobs

Add two repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | |
|---|---|
| `DATABASE_URL` | The Supabase pooler URL |
| `YOUTUBE_API_KEY` | Optional — absent, the ingest worker runs against its fixture provider |

`.github/workflows/scheduled.yml` then runs ingest nightly and the pipeline
hourly, and both can be triggered by hand from the Actions tab. Without
`DATABASE_URL` they skip cleanly rather than failing, so a fork does not collect
red checks for secrets it was never going to have.

Scheduled workflows are best-effort and GitHub delays them under load, sometimes
by a lot. That is fine for both: the pipeline is resumable and idempotent
(§10.1), so a missed run costs nothing and a re-run over finished work is free.

To move them to Render instead, add the two `type: cron` services back with
`plan: starter`. Render bills cron jobs by run time; at these schedules it is
roughly $2 a month, and it buys reliable scheduling and one place to look at
logs.

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
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
NEXT_PUBLIC_API_URL=https://loupe-api.onrender.com
NEXT_PUBLIC_AI_URL=https://loupe-ai.onrender.com
```

Older projects call that key `anon public`, and
`NEXT_PUBLIC_SUPABASE_ANON_KEY` is accepted for them.

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

The scheduled workflow runs the pipeline hourly with `USE_REAL_MODELS=false`,
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
| Render | Free × 3 | $0, with sleeping instances |
| GitHub Actions | Public repo | $0 for the two batch jobs |
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
