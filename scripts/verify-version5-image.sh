#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

image="${1:-amd-hackathon-version5:local}"

if [[ ! -s models/version5/nemotron-3-nano-4b.gguf ]]; then
  scripts/stage-version5-model.sh
fi

docker build -f Dockerfile.version5 -t "$image" .

compressed_bytes="$(docker save "$image" | gzip -c | wc -c | tr -d ' ')"
limit_bytes=$((10 * 1024 * 1024 * 1024))
if (( compressed_bytes >= limit_bytes )); then
  echo "compressed image exceeds 10 GB: $compressed_bytes bytes" >&2
  exit 1
fi

docker run --rm --memory=4g --cpus=2 "$image" amd-router preflight
printf 'compressed_image_bytes=%s\n' "$compressed_bytes"
