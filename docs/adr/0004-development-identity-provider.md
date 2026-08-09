# ADR 0004 — A development identity provider

**Status:** Accepted, 9 Aug 2026.
**Amends:** nothing. §5's service list gains a service that never deploys.

## The decision

`services/auth` is a small GoTrue-compatible identity provider for local
development. It issues the same HS256 tokens a hosted Supabase project issues,
signed with the same secret, and the core API verifies them through the code
path it already had.

It refuses to start unless `ENVIRONMENT=local`.

## Why

Every authenticated feature in Loupe was written, tested server-side, and never
once exercised from a browser. Comments, history, watch progress, playlists,
subscriptions, downloads, notification read state — all of it complete, all of
it unverified end to end. Five phase gates were partial for that one reason, and
the README's "what I would do next" put provisioning as the highest-value hour
available.

The blocker was never the code. It was that verifying it needed a hosted
Supabase project, and the alternative — `supabase start` — needs Docker, which
this machine does not have.

Creating that project is not something I can do on someone's behalf: it means
signing up for a service under their name. So the choice was between leaving
five gates partial indefinitely, or providing an identity provider that runs
here.

## Why it imitates GoTrue rather than being simpler

The web app talks to auth through `@supabase/ssr`, which owns cookie handling,
session storage and token refresh. A simpler bespoke endpoint would have meant
rewriting that client, and then the sign-in path exercised in development would
be different code from the one that runs in production. The path that never runs
is the path that breaks.

Speaking GoTrue's HTTP shape means **zero web application changes**. Two
environment variables point at `127.0.0.1:8041` instead of a Supabase URL.
Pointing them at a real project instead requires deleting nothing.

## Why this is not the bypass §5.1 rejected

The core API's auth module says:

> There is deliberately no development bypass. A header that skips verification
> when ENVIRONMENT=local is one misconfigured deploy away from being an
> authentication bypass in production, and this repository is public.

That reasoning is right and it applies here with more force, because this is a
larger version of the same risk. So:

- **There is no second verification path.** The API does not know this service
  exists. It decodes an HS256 token, checks `aud`, requires `exp` and `sub`, and
  rejects anything that fails — exactly as before.
- **The tokens are ordinary.** Same algorithm, same claims, same secret. A token
  from this provider and one from Supabase are indistinguishable to everything
  downstream, which is the point: what gets verified in development is what runs
  in production.
- **It fails closed at startup.** Not a warning, not a log line. It raises and
  refuses to serve, with a message naming the variable, if `ENVIRONMENT` is
  anything but `local` or if no signing secret is configured. There is a test
  for both.
- **Its table is not in the migration chain.** `dev_auth_identities` is created
  by the service at startup rather than by `db/migrations`, because the
  migration chain is what runs against production and this table must never
  reach it.
- **It is in no deploy configuration.** No Vercel, Render, or Fly entry, and no
  Dockerfile.

Passwords are hashed with scrypt at the standard interactive work factor, salted
per password, and the stored hash carries its own parameters. Unknown accounts
are verified against a dummy hash so a login attempt costs the same whether the
address exists or not. None of that is required for a development tool; it is
there because a password store that teaches bad habits is worse than no password
store.

## What it does not do

No email confirmation, no password reset, no OAuth providers, no magic links, no
rate limiting, no account lockout. It is four endpoints: sign up, exchange a
password for a session, refresh, and identify the bearer.

If Loupe is ever deployed, Supabase Auth or another GoTrue deployment does all
of that properly, and this service does not travel with it.

## Consequences

Five gates moved from partial to met, and the moves were verified in a browser
rather than argued for: sign-in, comment posting, likes and subscriptions,
watch-progress writes, AI playlist composition, and download records all
completed a round trip through the real API for the first time.

It also surfaced a bug that only authenticated use could reach — see
`docs/audio-mode.md` on the HTTP-cache variant failure in downloads, which had
been misdiagnosed as a service-worker problem and only became reproducible once
downloads could be repeated with a real account.

The cost is a service in the tree that a reader has to be told is not part of
the product. This document is that telling, and the guard in `main.py` is what
makes it true rather than aspirational.
