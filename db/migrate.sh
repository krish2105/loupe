#!/usr/bin/env bash
# Apply pending migrations in order, once each.
#
# Usage:  DATABASE_URL=postgres://... ./db/migrate.sh
#         ./db/migrate.sh --status     # show what has run
#
# No ORM and no migration framework: the pipeline is Python, the web app is
# TypeScript, and a shared ORM would have to serve both. Plain SQL files plus a
# ledger table is the smallest thing that gives ordered, once-only application.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${DATABASE_URL:-postgres://localhost:5432/loupe_dev}"
PSQL=(psql "$DB" -v ON_ERROR_STOP=1 --quiet --no-psqlrc)

"${PSQL[@]}" -c "
  CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
  );" >/dev/null

if [[ "${1:-}" == "--status" ]]; then
  "${PSQL[@]}" -c "SELECT version, applied_at FROM schema_migrations ORDER BY version;"
  exit 0
fi

applied=0
for file in "$DIR"/migrations/*.sql; do
  version="$(basename "$file" .sql)"

  exists=$("${PSQL[@]}" --tuples-only --no-align \
    -c "SELECT 1 FROM schema_migrations WHERE version = '$version';")

  if [[ -n "$exists" ]]; then
    echo "  skip  $version"
    continue
  fi

  echo "  applying  $version"
  # Each migration runs inside one transaction together with its ledger entry, so a
  # failure leaves neither the schema change nor the record of it.
  "${PSQL[@]}" --single-transaction \
    -f "$file" \
    -c "INSERT INTO schema_migrations (version) VALUES ('$version');"
  applied=$((applied + 1))
done

echo "done — $applied migration(s) applied"
