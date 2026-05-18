#!/bin/sh
set -eu

exec streamlit run app/streamlit_app.py \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --browser.gatherUsageStats=false
