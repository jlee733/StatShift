#!/bin/sh
set -eu

PREFECT_API_URL="${PREFECT_API_URL:-http://prefect-server:4200/api}"
export PREFECT_API_URL
export PREFECT_SERVER_ANALYTICS_ENABLED="${PREFECT_SERVER_ANALYTICS_ENABLED:-false}"

HEALTH_URL="http://prefect-server:4200/api/health"
echo "Waiting for Prefect at ${HEALTH_URL}..."

TRIES=0
until python -c "
import urllib.request
urllib.request.urlopen('${HEALTH_URL}', timeout=5)
" 2>/dev/null; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -gt 90 ]; then
    echo "Prefect server not healthy after 3 minutes" >&2
    exit 1
  fi
  sleep 2
done

echo "Prefect ready. Starting ESPN scrape flow..."
exec python -m jobs.scrape_active_players
