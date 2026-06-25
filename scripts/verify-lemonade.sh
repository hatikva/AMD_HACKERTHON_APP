#!/usr/bin/env bash
set -Eeuo pipefail

if command -v ss >/dev/null 2>&1 && ss -ltn '( sport = :11434 )' | grep -q 11434; then
  echo "Ollama is still listening on 11434" >&2
  exit 1
fi

curl -fsS http://127.0.0.1:13305/api/v1/models >/dev/null
docker compose -f compose.dev.yml config | grep -q '127.0.0.1:13305:13305'

if docker compose -f compose.dev.yml config | grep -Ei 'cuda|rocm|vulkan|npu|device:'; then
  echo "accelerator or device configuration found in Compose output" >&2
  exit 1
fi

echo "Lemonade verification checks passed"
