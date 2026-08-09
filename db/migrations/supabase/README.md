# Supabase-only migrations

These run **after** the numbered migrations, and only against a hosted Supabase
project. They are kept out of `db/migrations/` because they reference the `auth`
schema, which does not exist in a plain Postgres instance — and Phase 0 is
developed against plain local Postgres (no Docker on the build machine).

Apply with:

```bash
DATABASE_URL="$SUPABASE_DB_URL" psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/supabase/0001_auth_link.sql
```
