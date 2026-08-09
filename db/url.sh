#!/usr/bin/env bash
# Build a connection URL without the password touching shell history.
#
#   export LOUPE_DB="$(./db/url.sh 'postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:6543/postgres')"
#   psql "$LOUPE_DB" -c "SELECT count(*) FROM videos"
#
# Paste the URI exactly as Supabase prints it, placeholder and all. The password
# is read without echo and percent-encoded here.
#
# Hand-encoding is the step that keeps going wrong, and its failure is
# unhelpful: an unencoded @ splits the URL at the wrong place, so libpq reports
# a hostname made of half the password, or an authentication failure against a
# username nobody typed. Neither points at the password.
#
# Reading it rather than taking it as an argument also keeps it out of shell
# history and off the screen — worth doing for anything that is one screenshot
# away from being public.
set -euo pipefail

TEMPLATE="${1:-}"

if [[ -z "$TEMPLATE" ]]; then
  cat >&2 <<'USAGE'
Usage: ./db/url.sh '<connection URI with the password placeholder left in>'

From Supabase → Connect → Direct → Transaction pooler → URI. Single-quote it.

  export LOUPE_DB="$(./db/url.sh 'postgresql://postgres.abc:[YOUR-PASSWORD]@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres')"
USAGE
  exit 2
fi

# Prompts go to stderr so the URL is the only thing on stdout and $( ) captures
# it cleanly.
printf 'Database password (not shown): ' >&2
read -rs PASSWORD
printf '\n' >&2

if [[ -z "$PASSWORD" ]]; then
  echo "No password entered." >&2
  exit 2
fi

ENCODED="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$PASSWORD")"

# Every placeholder Supabase or this project has used.
URL="$TEMPLATE"
for placeholder in '[YOUR-PASSWORD]' 'YOUR-PASSWORD' 'YOURPASSWORD' '<password>' '[PASSWORD]'; do
  URL="${URL//"$placeholder"/$ENCODED}"
done

if [[ "$URL" == "$TEMPLATE" ]]; then
  echo "No password placeholder found in that URI — nothing was substituted." >&2
  echo "Paste it exactly as Supabase prints it, with [YOUR-PASSWORD] left in." >&2
  exit 2
fi

printf '%s\n' "$URL"
