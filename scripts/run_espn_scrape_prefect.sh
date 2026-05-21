#!/usr/bin/env sh
# Run ESPN scrape via the Prefect flow against a local Prefect server.
#
# 1. Start server (if needed): ./scripts/start_prefect_server.sh
# 2. Run this script (uses caffeinate on macOS to prevent sleep)
#
# Usage:
#   ./scripts/run_espn_scrape_prefect.sh
#   ./scripts/run_espn_scrape_prefect.sh background   # nohup + log file
#   ./scripts/run_espn_scrape_prefect.sh docker       # compose scrape container

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:-foreground}"

export PREFECT_API_URL="${PREFECT_API_URL:-http://127.0.0.1:4200/api}"
export PREFECT_SERVER_ANALYTICS_ENABLED="${PREFECT_SERVER_ANALYTICS_ENABLED:-false}"

wait_for_prefect() {
  echo "Checking Prefect API at ${PREFECT_API_URL}..."
  TRIES=0
  until curl -sf "http://127.0.0.1:4200/api/health" >/dev/null 2>&1; do
    TRIES=$((TRIES + 1))
    if [ "$TRIES" -eq 1 ]; then
      echo "Prefect server not reachable. Starting Docker server..."
      sh "${ROOT}/scripts/start_prefect_server.sh" docker
    fi
    if [ "$TRIES" -gt 60 ]; then
      echo "Start Prefect first: ./scripts/start_prefect_server.sh" >&2
      exit 1
    fi
    sleep 2
  done
  echo "Prefect server OK — UI: http://127.0.0.1:4200"
}

if [ "$MODE" = "docker" ]; then
  wait_for_prefect
  echo "Running scrape in Docker (Prefect + sync profiles)..."
  exec docker compose --profile prefect --profile sync run --rm espn-active-sync
fi

if [ -x "${ROOT}/.venv/bin/python" ]; then
  PYTHON="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "No Python found. Create a venv first." >&2
  exit 1
fi

INNER="${PYTHON} -m jobs.scrape_active_players"

if [ "$MODE" = "background" ]; then
  LOG_DIR="${ROOT}/data/logs"
  mkdir -p "$LOG_DIR"
  STAMP="$(date +%Y%m%d_%H%M%S)"
  LOG_FILE="${LOG_DIR}/espn_scrape_${STAMP}.log"
  PID_FILE="${LOG_DIR}/espn_scrape.pid"
  wait_for_prefect
  if command -v caffeinate >/dev/null 2>&1; then
    WRAP="caffeinate -dims"
  else
    WRAP=""
  fi
  echo "Log: ${LOG_FILE}"
  nohup sh -c "${WRAP} sh -c 'cd \"$ROOT\" && export PREFECT_API_URL=\"$PREFECT_API_URL\" PREFECT_SERVER_ANALYTICS_ENABLED=false && $INNER'" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "PID $(cat "$PID_FILE") — tail -f ${LOG_FILE}"
  exit 0
fi

wait_for_prefect
if command -v caffeinate >/dev/null 2>&1; then
  echo "Preventing sleep while scrape runs (caffeinate)..."
  exec caffeinate -dims sh -c "cd \"$ROOT\" && export PREFECT_API_URL=\"$PREFECT_API_URL\" PREFECT_SERVER_ANALYTICS_ENABLED=false && $INNER"
else
  exec sh -c "cd \"$ROOT\" && export PREFECT_API_URL=\"$PREFECT_API_URL\" PREFECT_SERVER_ANALYTICS_ENABLED=false && $INNER"
fi
