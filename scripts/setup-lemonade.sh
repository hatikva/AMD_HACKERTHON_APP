#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

scripts/stop-ollama.sh

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command is unavailable" >&2
  exit 1
fi

docker compose version >/dev/null
docker compose -f compose.dev.yml up -d --build

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:13305/api/v1/models >/dev/null 2>&1 || curl -fsS http://127.0.0.1:13305/live >/dev/null 2>&1; then
    echo "Lemonade is reachable"
    break
  fi
  sleep 2
done

if ! curl -fsS http://127.0.0.1:13305/api/v1/models >/dev/null 2>&1 && ! curl -fsS http://127.0.0.1:13305/live >/dev/null 2>&1; then
  echo "Timed out waiting for Lemonade on 127.0.0.1:13305" >&2
  docker compose -f compose.dev.yml logs --tail=100 lemonade >&2 || true
  exit 1
fi

for model in Qwen3-4B-Instruct-2507-GGUF Phi-4-mini-instruct-GGUF LFM2.5-1.2B-Instruct-GGUF; do
  echo "Pulling $model"
  docker compose -f compose.dev.yml exec lemonade lemonade pull "$model"
done

docker compose -f compose.dev.yml exec lemonade lemonade list || true
docker system df || true
