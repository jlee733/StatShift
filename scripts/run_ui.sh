#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
