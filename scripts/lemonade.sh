#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command is unavailable" >&2
  exit 1
fi

if ! docker compose -f compose.dev.yml ps lemonade >/dev/null 2>&1; then
  echo "lemonade compose service is unavailable; run scripts/setup-lemonade.sh first" >&2
  exit 1
fi

docker compose -f compose.dev.yml exec lemonade ./lemonade-server "$@"
