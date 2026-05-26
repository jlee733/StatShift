#!/bin/sh
# Load the configured model into Ollama memory before the UI accepts Ask queries.

set -eu

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-batiai/gemma4-e2b:q4}"
MAX_WAIT="${OLLAMA_WARMUP_MAX_WAIT:-900}"

echo "Waiting for Ollama at ${OLLAMA_HOST}..."
deadline=$(( $(date +%s) + MAX_WAIT ))
until ollama list >/dev/null 2>&1; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "Ollama did not become ready within ${MAX_WAIT}s" >&2
        exit 1
    fi
    sleep 2
done

echo "Warming up model ${MODEL} (first load can take several minutes)..."
ollama run "$MODEL" "Reply with exactly: ready" </dev/null

echo "Ollama model ${MODEL} is loaded and ready."
