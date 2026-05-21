#!/usr/bin/env sh
# Run the ESPN active-player scrape in the background with logs.
#
# If the machine sleeps, the scrape pauses. On macOS this uses `caffeinate` to
# prevent sleep while the job runs (use AC power for long runs). For laptop-closed
# or multi-day reliability, run on a remote server/VM (see README).
#
# Usage:
#   ./scripts/run_espn_scrape_background.sh
#   ./scripts/run_espn_scrape_background.sh docker
#
# Logs: data/logs/espn_scrape_<timestamp>.log
# PID:  data/logs/espn_scrape.pid

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="${ROOT}/data/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/espn_scrape_${STAMP}.log"
PID_FILE="${LOG_DIR}/espn_scrape.pid"
MODE="${1:-local}"

if [ "$MODE" = "docker" ]; then
  INNER="docker compose --profile sync run --rm espn-active-sync"
else
  INNER="python -m jobs.scrape_active_players"
fi

if command -v caffeinate >/dev/null 2>&1; then
  CMD="caffeinate -dims sh -c 'cd \"$ROOT\" && $INNER'"
  CAFFEINATE_MSG="yes (macOS — system stays awake while scrape runs)"
else
  CMD="sh -c 'cd \"$ROOT\" && $INNER'"
  CAFFEINATE_MSG="no — use AC power + disable sleep, or run on a remote host"
fi

echo "Starting ESPN scrape (mode=${MODE})"
echo "Log file: ${LOG_FILE}"
echo "Prevent sleep: ${CAFFEINATE_MSG}"

nohup sh -c "$CMD" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
echo "PID $(cat "$PID_FILE")"
echo "Follow progress: tail -f ${LOG_FILE}"
