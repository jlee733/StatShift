#!/bin/sh
# Pull Ollama models for StatShift (skips models that are already cached)

set -e

ensure_model() {
    model_name="$1"
    if ollama list | awk '{print $1}' | grep -Fxq "$model_name"; then
        echo "✓ $model_name is already cached, skipping download."
    else
        echo "↓ Pulling $model_name..."
        ollama pull "$model_name"
        echo "✓ $model_name pulled successfully."
    fi
}

ensure_model "gemma2:latest"
ensure_model "llama3:latest"

echo "All models ready!"
