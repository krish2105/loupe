#!/usr/bin/env bash
# Prepare a hosted database: extension, schema, auth link, and optionally a
# catalogue to look at.
#
#   ./db/setup-hosted.sh "<url>" --seed
#   ./db/setup-hosted.sh "<url with [YOUR-PASSWORD] left in>" --password '<pw>' --seed
#
# Four commands with the same long URL repeated in each is four chances to paste
# it wrong, and the failure when you do is a connection error that looks like a
# credentials problem. One script, one paste.
#
# The URL is never echoed. It contains a password, and a terminal is a log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

URL=""
PASSWORD=""
SEED=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed)     SEED="yes"; shift ;;
    --password) PASSWORD="${2:-}"; shift 2 ;;
    -h|--help)  URL=""; break ;;
    *)          URL="$1"; shift ;;
  esac
done

if [[ -z "$URL" ]]; then
  cat >&2 <<'USAGE'
Usage:
  ./db/setup-hosted.sh "<connection string>" [--seed]
  ./db/setup-hosted.sh "<connection string with [YOUR-PASSWORD] left in>" \
      --password '<the password>' [--seed]

The second form is easier to get right. Paste the URI exactly as Supabase gives
it, placeholder and all, and pass the password separately — the script
substitutes it and percent-encodes it, which is the step that otherwise produces
an authentication error blaming the username.

Supabase → Connect → Direct → Transaction pooler → URI.

Quote both arguments. Passwords contain characters the shell would interpret.
USAGE
  exit 2
fi

if [[ -n "$PASSWORD" ]]; then
  # Encoded here rather than by hand. A password with @ in it splits the URL at
  # the wrong place and Postgres reports a username that does not exist, which
  # sends people looking in entirely the wrong direction.
  encoded="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$PASSWORD")"
  URL="${URL//\[YOUR-PASSWORD\]/$encoded}"
fi

case "$URL" in
  *"[YOUR-PASSWORD]"*)
    cat >&2 <<'PLACEHOLDER'
The password placeholder is still in the URL. Either replace it yourself, or
leave it in place and pass the password separately:

  ./db/setup-hosted.sh "<url with [YOUR-PASSWORD]>" --password '<password>'

Reset it under Project Settings → Database if you do not have it.
PLACEHOLDER
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

echo "2/4  extensions"
# Both of the ones migration 0001 needs. Checked together rather than letting
# the second one fail at step 3, after the first has already succeeded — a
# half-applied setup is worse to reason about than one that stopped.
missing=()
for extension in vector pgcrypto; do
  if psql_quiet --tuples-only --no-align \
       -c "SELECT 1 FROM pg_extension WHERE extname = '$extension'" 2>/dev/null | grep -q 1; then
    echo "     $extension already enabled"
    continue
  fi

  # Two spellings. Supabase keeps extensions in a dedicated schema and some
  # projects refuse the bare form; trying both is cheaper than asking someone to
  # work out which kind of project they have.
  if psql "$URL" -v ON_ERROR_STOP=1 --quiet --no-psqlrc \
       -c "CREATE EXTENSION IF NOT EXISTS $extension WITH SCHEMA extensions" >/dev/null 2>&1 \
     || psql "$URL" -v ON_ERROR_STOP=1 --quiet --no-psqlrc \
       -c "CREATE EXTENSION IF NOT EXISTS $extension" >/dev/null 2>&1; then
    echo "     $extension enabled"
  else
    echo "     $extension could not be enabled from here"
    missing+=("$extension")
  fi
done

if (( ${#missing[@]} )); then
  # The real message, once, rather than a guess. Hiding this is what made the
  # first version of this script useless at the one moment it mattered.
  echo >&2
  echo "     Postgres said, for ${missing[0]}:" >&2
  psql "$URL" -v ON_ERROR_STOP=1 --quiet --no-psqlrc \
    -c "CREATE EXTENSION IF NOT EXISTS ${missing[0]}" 2>&1 | sed 's/^/       /' >&2

  cat >&2 <<FIX

     Enable ${missing[*]} in the dashboard instead. Newer projects do not let
     the connection role create extensions:

       Database → Extensions → search the name → toggle on

     or in the SQL editor:

FIX
  for extension in "${missing[@]}"; do
    echo "       create extension if not exists $extension with schema extensions;" >&2
  done
  echo >&2
  echo "     Then run this script again. It skips whatever is already enabled." >&2
  exit 1
fi

echo "3/4  applying migrations"
DATABASE_URL="$URL" "$ROOT/db/migrate.sh" | sed 's/^/     /'

echo "4/4  linking profiles to auth.users"
# Hosted-only: local development has no `auth` schema, which is why this is a
# separate file rather than a migration in the chain.
psql_quiet -f "$ROOT/db/migrations/supabase/0001_auth_link.sql" >/dev/null
echo "     ok"

if [[ "$SEED" == "yes" ]]; then
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
