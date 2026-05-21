#!/bin/sh
set -eu

exec streamlit run ui/app.py \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --browser.gatherUsageStats=false
