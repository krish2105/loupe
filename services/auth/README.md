# Development identity provider

Not part of the product. It exists so a developer can sign in on their own
machine, and it refuses to start anywhere else.

Full reasoning, including why it is not the auth bypass §5.1 rejected:
[ADR 0004](../../docs/adr/0004-development-identity-provider.md).

## Running it

```bash
export SUPABASE_JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

cd services/auth
DATABASE_URL=postgres://localhost:5432/loupe_dev uv run uvicorn app.main:app --port 8041
```

The core API needs the same secret, or it will reject every token this issues:

```bash
cd services/api
SUPABASE_JWT_SECRET="$SUPABASE_JWT_SECRET" \
DATABASE_URL=postgres://localhost:5432/loupe_dev \
  uv run uvicorn app.main:app --port 8010
```

Then point the web app at it in `web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:8041
NEXT_PUBLIC_SUPABASE_ANON_KEY=local-development-anon-key
```

The anon key is not checked. It exists because `createBrowserClient` requires a
non-empty second argument.

## What it implements

Four endpoints, which is everything `@supabase/ssr` needs for email and password:

- `POST /auth/v1/signup`
- `POST /auth/v1/token?grant_type=password`
- `POST /auth/v1/token?grant_type=refresh_token`
- `GET /auth/v1/user`
- `POST /auth/v1/logout`

No email confirmation, no password reset, no OAuth, no magic links, no rate
limiting. Supabase Auth does all of that; this does not pretend to.
