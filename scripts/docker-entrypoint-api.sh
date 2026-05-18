#!/bin/sh
set -eu

python scripts/init_db.py
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
