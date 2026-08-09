#!/usr/bin/env bash
# Start everything Loupe needs locally, in one command.
#
#   ./dev.sh          start web, api, ai and auth
#   ./dev.sh --stop   stop whatever this script started
#
# Five processes with a shared signing secret and four ports is more setup than
# a README paragraph survives, so it is a script. The alternative is a paragraph
# that goes stale and a person debugging a token mismatch on their first day.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 8000 and 8020 belong to other applications on the build machine. Verified,
# not assumed — this cost an afternoon once.
API_PORT=8010
AI_PORT=8031
AUTH_PORT=8041
WEB_PORT=3000

export DATABASE_URL="${DATABASE_URL:-postgres://localhost:5432/loupe_dev}"
LOGS="$ROOT/.dev-logs"

stop() {
  for port in $API_PORT $AI_PORT $AUTH_PORT $WEB_PORT; do
    pids="$(lsof -ti:"$port" 2>/dev/null || true)"
    [ -n "$pids" ] && { echo "  stopping :$port"; echo "$pids" | xargs kill 2>/dev/null || true; }
  done
  echo "stopped"
}

if [[ "${1:-}" == "--stop" ]]; then stop; exit 0; fi

# The signing secret is shared by the auth service, which mints tokens, and the
# API, which verifies them. Generated once and kept out of git: a mismatch shows
# up as every request returning 401 with nothing obviously wrong.
SECRET_FILE="$ROOT/.env.local.shared"
if [[ ! -f "$SECRET_FILE" ]]; then
  echo "SUPABASE_JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" > "$SECRET_FILE"
  echo "generated $SECRET_FILE"
fi
# shellcheck disable=SC1090
source "$SECRET_FILE"
export SUPABASE_JWT_SECRET

if [[ ! -f "$ROOT/web/.env.local" ]]; then
  cat > "$ROOT/web/.env.local" <<ENV
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:$AUTH_PORT
NEXT_PUBLIC_SUPABASE_ANON_KEY=local-development-anon-key
NEXT_PUBLIC_API_URL=http://127.0.0.1:$API_PORT
NEXT_PUBLIC_AI_URL=http://127.0.0.1:$AI_PORT
ENV
  echo "generated web/.env.local"
fi

mkdir -p "$LOGS"
stop >/dev/null 2>&1 || true

start() {
  local name="$1" dir="$2" port="$3"; shift 3
  echo "  :$port  $name"
  # stdin closed and both streams redirected, so the children hold no handle on
  # this script's terminal. Without that, piping ./dev.sh into anything hangs
  # forever: the pipe stays open as long as a background process could still
  # write to it, and these run until they are killed.
  ( cd "$dir" && nohup "$@" > "$LOGS/$name.log" 2>&1 < /dev/null & )
}

echo "starting:"
start auth services/auth "$AUTH_PORT" \
  env ENVIRONMENT=local uv run uvicorn app.main:app --port "$AUTH_PORT"
start api services/api "$API_PORT" \
  uv run uvicorn app.main:app --port "$API_PORT"
start ai services/ai "$AI_PORT" \
  env USE_REAL_EMBEDDINGS=true uv run uvicorn app.main:app --port "$AI_PORT"
start web web "$WEB_PORT" \
  pnpm dev --port "$WEB_PORT"

echo
# Next compiles the first route on demand, so the web check is the slow one and
# two minutes is not generous.
echo -n "waiting"
for _ in $(seq 1 90); do
  if curl -sf --max-time 2 "http://127.0.0.1:$AUTH_PORT/health" >/dev/null 2>&1 \
     && curl -sf --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1 \
     && curl -sf --max-time 20 -o /dev/null "http://127.0.0.1:$WEB_PORT/" 2>/dev/null; then
    echo " ready"
    echo
    echo "  http://localhost:$WEB_PORT"
    echo "  logs in .dev-logs/, stop with ./dev.sh --stop"
    exit 0
  fi
  echo -n "."
  sleep 2
done

echo " timed out — check .dev-logs/"
exit 1
