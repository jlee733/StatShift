#!/usr/bin/env sh
# Start a local Prefect server (Docker by default).
#
# UI:  http://127.0.0.1:4200
# API: http://127.0.0.1:4200/api
#
# Usage:
#   ./scripts/start_prefect_server.sh          # Docker (detached)
#   ./scripts/start_prefect_server.sh local    # venv: prefect server start (foreground)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:-docker}"

if [ "$MODE" = "local" ]; then
  if [ -x "${ROOT}/.venv/bin/prefect" ]; then
    PREFECT="${ROOT}/.venv/bin/prefect"
  elif command -v prefect >/dev/null 2>&1; then
    PREFECT="prefect"
  else
    echo "Install Prefect: .venv/bin/pip install -r requirements.txt" >&2
    exit 1
  fi
  export PREFECT_API_URL="${PREFECT_API_URL:-http://127.0.0.1:4200/api}"
  export PREFECT_SERVER_ANALYTICS_ENABLED="${PREFECT_SERVER_ANALYTICS_ENABLED:-false}"
  echo "Starting Prefect server (foreground). UI: http://127.0.0.1:4200"
  echo "In another terminal: ./scripts/run_espn_scrape_prefect.sh"
  exec "$PREFECT" server start --host 0.0.0.0
fi

echo "Starting Prefect server container..."
docker compose --profile prefect up -d prefect-server

echo "Waiting for Prefect API..."
TRIES=0
until curl -sf "http://127.0.0.1:4200/api/health" >/dev/null 2>&1; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -gt 60 ]; then
    echo "Prefect server did not become healthy. Check: docker compose --profile prefect logs prefect-server" >&2
    exit 1
  fi
  sleep 2
done

echo "Prefect server is up."
echo "  UI:  http://127.0.0.1:4200"
echo "  API: http://127.0.0.1:4200/api"
echo "Run scrape: ./scripts/run_espn_scrape_prefect.sh"
