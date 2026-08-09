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

# Replace whatever is sitting in the password position, whether that is a
# placeholder, a stale password, or an unencoded one.
#
# The first version only substituted known placeholders and refused otherwise,
# which failed on the very next attempt: the URI had a real password in it
# already and the script said it could not find a placeholder, which is true and
# useless. The password position is unambiguous — between the first colon after
# the scheme and the last @ before the host — so there is no need to guess.
URL="$(TEMPLATE="$TEMPLATE" ENCODED="$ENCODED" python3 - <<'PYTHON'
import os
import sys

template = os.environ["TEMPLATE"]
encoded = os.environ["ENCODED"]

if "://" not in template:
    sys.exit("That does not look like a connection URI (no scheme).")

scheme, rest = template.split("://", 1)

if "@" not in rest:
    sys.exit("That URI has no user@host part, so there is nowhere to put a password.")

# rsplit: a password may itself contain an @ if it was pasted unencoded, and the
# host is always after the last one.
credentials, host = rest.rsplit("@", 1)
user = credentials.split(":", 1)[0]

print(f"{scheme}://{user}:{encoded}@{host}")
PYTHON
)"

printf '%s\n' "$URL"
