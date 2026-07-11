#!/usr/bin/env bash
set -euo pipefail

image="${ANALYTICS_UI_IMAGE:-amd-hackathon:version6-analytics-ui}"
port="${UI_PORT:-18084}"

podman rm -f amd-version6-analytics-ui >/dev/null 2>&1 || true

podman run -d \
  --name amd-version6-analytics-ui \
  -p "127.0.0.1:${port}:${port}" \
  -e UI_HOST=0.0.0.0 \
  -e "UI_PORT=${port}" \
  -v "$PWD/qualification/results:/app/qualification/results:ro,Z" \
  "$image"

echo "http://127.0.0.1:${port}"
