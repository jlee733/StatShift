#!/usr/bin/env sh
# Run the ESPN active-player scrape in the background with logs.
#
# Default (prefect): local Prefect server + flow + caffeinate (macOS).
#
# Usage:
#   ./scripts/run_espn_scrape_background.sh           # Prefect (recommended)
#   ./scripts/run_espn_scrape_background.sh sync    # no Prefect
#   ./scripts/run_espn_scrape_background.sh docker    # Docker Prefect + scrape
#
# Logs: data/logs/espn_scrape_<timestamp>.log (prefect/sync modes)

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-prefect}"

case "$MODE" in
  prefect)
    exec sh "${ROOT}/scripts/run_espn_scrape_prefect.sh" background
    ;;
  sync)
    LOG_DIR="${ROOT}/data/logs"
    mkdir -p "$LOG_DIR"
    STAMP="$(date +%Y%m%d_%H%M%S)"
    LOG_FILE="${LOG_DIR}/espn_scrape_${STAMP}.log"
    PID_FILE="${LOG_DIR}/espn_scrape.pid"
    if [ -x "${ROOT}/.venv/bin/python" ]; then
      PYTHON="${ROOT}/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON="python3"
    else
      echo "No Python found." >&2
      exit 1
    fi
    INNER="${PYTHON} -m jobs.scrape_active_players_sync"
    if command -v caffeinate >/dev/null 2>&1; then
      CMD="caffeinate -dims sh -c 'cd \"$ROOT\" && $INNER'"
    else
      CMD="sh -c 'cd \"$ROOT\" && $INNER'"
    fi
    echo "Log: ${LOG_FILE}"
    nohup sh -c "$CMD" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    echo "PID $(cat "$PID_FILE") — tail -f ${LOG_FILE}"
    ;;
  docker)
    exec sh "${ROOT}/scripts/run_espn_scrape_prefect.sh" docker
    ;;
  *)
    echo "Unknown mode: ${MODE} (use prefect, sync, or docker)" >&2
    exit 1
    ;;
esac
