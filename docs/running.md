# Running Loupe locally

Everything works on one machine with no hosted services, including sign-in.

## Requirements

Node 22+, pnpm, Python 3.11+, [uv](https://docs.astral.sh/uv/), and PostgreSQL 17
with pgvector.

```bash
brew install postgresql@17 pgvector node pnpm uv
brew services start postgresql@17
```

## First run

```bash
git clone https://github.com/krish2105/loupe && cd loupe

createdb loupe_dev
DATABASE_URL=postgres://localhost:5432/loupe_dev ./db/migrate.sh

# A browsable catalogue: 17 owned talks, 3,048 referenced, 8 shorts, 6 episodes
psql postgres://localhost:5432/loupe_dev -f db/seed/0001_demo_catalogue.sql
psql postgres://localhost:5432/loupe_dev -f db/seed/0002_shorts.sql
psql postgres://localhost:5432/loupe_dev -f db/seed/0003_audio.sql

(cd web && pnpm install)

./dev.sh
```

`./dev.sh` starts four processes and prints a URL. `./dev.sh --stop` stops them,
and logs land in `.dev-logs/`.

| | Port | |
|---|---|---|
| web | 3000 | Next.js |
| api | 8010 | CRUD, feeds, collections, authorisation |
| ai | 8031 | Summaries, ask-video, semantic search, playlists |
| auth | 8041 | Development identity provider ([ADR 0004](adr/0004-development-identity-provider.md)) |

Ports 8000 and 8020 are avoided because other applications on the original build
machine use them. That was verified rather than assumed, after an afternoon lost
to it.

On first run the script generates two files and tells you it did:

- `.env.local.shared` — the JWT signing secret, shared by the auth service that
  mints tokens and the API that verifies them. Gitignored. A mismatch here shows
  up as every request returning 401 with nothing else obviously wrong, which is
  why it is generated once rather than typed twice.
- `web/.env.local` — pointing the web app at the three local services.

## Indexing the transcripts

The seeded talks arrive at `transcoded`. Nothing is searchable until the
pipeline runs:

```bash
cd services/pipeline
DATABASE_URL=postgres://localhost:5432/loupe_dev uv run python -m app.run --all
```

It is resumable and idempotent (§10.1), so re-running it costs nothing for work
already done. Afterwards the AI panel, semantic search, chapters and the
time-synced transcript all have something to work with.

**The transcripts are fixture output.** The seeded media points at a public
reference stream with no speech in it, so a fixture transcriber generates text
and stores it with `engine = 'fixture'`. The stage machine, chunker,
normaliser, drift detection and chapter assembly are real; only the audio is
not. Setting `USE_REAL_MODELS=true` runs Whisper instead, on real audio.

## Signing in

Create an account at <http://localhost:3000/login>. It is a real account: a row
in `users`, a scrypt-hashed credential, an HS256 token the API verifies through
the same code path a hosted Supabase project's token travels.

Everything behind a session then works: comments, likes, subscriptions, watch
history and resume, playlists, AI playlist composition, downloads, notification
read state.

## Using a real Supabase project instead

Replace two variables in `web/.env.local` and restart:

```
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Then give the API that project's JWT secret rather than the generated one, and
apply the schema plus `db/migrations/supabase/0001_auth_link.sql` to its
database. No application code changes: the same client, the same verification, a
different issuer.

## Optional services

Neither is needed to browse, watch, ask questions or sign in.

**Media** (`services/media`, Bunny signing and webhooks) needs a Bunny Stream
account. Without one, uploads and transcoding are unavailable and the seeded
catalogue plays from its reference stream.

**Ingest** (`services/ingest`, the nightly Class B sync) runs against a
deterministic fixture provider unless `YOUTUBE_API_KEY` is set. The worker, the
quota ledger, the idempotency and the write path are all real; only the upstream
is not.

## Tests

```bash
(cd web && pnpm test && pnpm lint && npx tsc --noEmit)

for s in api ai auth eval recsys media ingest pipeline; do
  (cd "services/$s" && DATABASE_URL=postgres://localhost:5432/loupe_dev uv run pytest -q)
done

psql postgres://localhost:5432/loupe_dev -f db/tests/constraints.sql
```

The API, auth and schema suites need a database. The rest do not, which is
deliberate: the rules worth testing were extracted as pure functions precisely
so they could be tested without one.
