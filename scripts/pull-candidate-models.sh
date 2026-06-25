#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for model in Qwen3-4B-Instruct-2507-GGUF Phi-4-mini-instruct-GGUF LFM2.5-1.2B-Instruct-GGUF; do
  echo "Pulling $model"
  if command -v timeout >/dev/null 2>&1; then
    timeout "${LEMONADE_MODEL_PULL_TIMEOUT_SECONDS:-3600}" docker compose -f compose.dev.yml exec lemonade ./lemonade-server pull "$model"
  else
    docker compose -f compose.dev.yml exec lemonade ./lemonade-server pull "$model"
  fi
done

docker compose -f compose.dev.yml exec lemonade ./lemonade-server list || true
docker system df || true
