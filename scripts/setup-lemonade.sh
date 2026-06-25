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
build_timeout="${LEMONADE_BUILD_TIMEOUT_SECONDS:-1200}"
if command -v timeout >/dev/null 2>&1; then
  timeout "$build_timeout" docker compose -f compose.dev.yml up -d --build
else
  docker compose -f compose.dev.yml up -d --build
fi

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

if [[ "${LEMONADE_PULL_MODELS:-0}" == "1" ]]; then
  scripts/pull-candidate-models.sh
else
  echo "Lemonade started. Candidate model pulls are a separate pipeline stage."
fi
