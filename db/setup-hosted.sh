#!/usr/bin/env bash
# Prepare a hosted database: extension, schema, auth link, and optionally a
# catalogue to look at.
#
#   ./db/setup-hosted.sh "postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres"
#   ./db/setup-hosted.sh "<url>" --seed
#
# Four commands with the same long URL repeated in each is four chances to paste
# it wrong, and the failure when you do is a connection error that looks like a
# credentials problem. One script, one paste.
#
# The URL is never echoed. It contains a password, and a terminal is a log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

URL="${1:-}"
SEED="${2:-}"

if [[ -z "$URL" ]]; then
  cat >&2 <<'USAGE'
Usage: ./db/setup-hosted.sh "<connection string>" [--seed]

Supabase → Connect → Direct → Transaction pooler → URI, with [YOUR-PASSWORD]
replaced by the real password. Quote it: passwords contain characters the shell
would otherwise interpret.
USAGE
  exit 2
fi

case "$URL" in
  *"[YOUR-PASSWORD]"*)
    echo "The password placeholder is still in the URL. Replace [YOUR-PASSWORD]" >&2
    echo "with the real one, or reset it in Project Settings → Database." >&2
    exit 2
    ;;
esac

psql_quiet() { psql "$URL" -v ON_ERROR_STOP=1 --quiet --no-psqlrc "$@"; }

echo "1/4  connecting"
if ! psql_quiet -c "SELECT 1" >/dev/null 2>&1; then
  cat >&2 <<'FAILED'
     could not connect.

     Most likely causes, in order:
       - the password is wrong, or still needs percent-encoding if it contains
         any of  @ : / ? # [ ] %
       - the URL is the direct connection rather than the pooler. The pooler
         host contains "pooler" and the port is 6543
       - the project is still starting; a new one takes a minute
FAILED
  exit 1
fi
echo "     ok"

echo "2/4  enabling pgvector"
if psql_quiet -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null 2>&1; then
  echo "     ok"
else
  # Some plans do not allow creating it over the wire. The dashboard always can.
  echo "     could not create it from here — enable it in the dashboard under" >&2
  echo "     Database → Extensions → vector, then run this again." >&2
  exit 1
fi

echo "3/4  applying migrations"
DATABASE_URL="$URL" "$ROOT/db/migrate.sh" | sed 's/^/     /'

echo "4/4  linking profiles to auth.users"
# Hosted-only: local development has no `auth` schema, which is why this is a
# separate file rather than a migration in the chain.
psql_quiet -f "$ROOT/db/migrations/supabase/0001_auth_link.sql" >/dev/null
echo "     ok"

if [[ "$SEED" == "--seed" ]]; then
  echo
  echo "seeding a catalogue"
  for file in 0001_demo_catalogue 0002_shorts 0003_audio; do
    echo "     $file"
    psql_quiet -f "$ROOT/db/seed/$file.sql" >/dev/null
  done
fi

echo
psql_quiet --tuples-only --no-align -c "
  SELECT 'videos: ' || count(*) FROM videos
  UNION ALL SELECT 'channels: ' || count(*) FROM channels
  UNION ALL SELECT 'tables: ' || count(*) FROM information_schema.tables
                                  WHERE table_schema = 'public';" | sed 's/^/  /'

echo
echo "done. Next: put this URL into Render and into the repository's"
echo "Actions secrets, and the JWT secret into Render's API service."
