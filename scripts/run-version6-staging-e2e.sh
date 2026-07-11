#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${OLLAMA_API_KEY:-}" ]]; then
  echo "OLLAMA_API_KEY must be configured in the process environment" >&2
  exit 2
fi

image="${STAGING_IMAGE:-ghcr.io/hatikva/amd-hackathon-app:version6-staging-ollama-cloud-1cebdfc}"

PYTHONPATH="${PYTHONPATH:-src}" python3 -m amd_hackathon_app.staging_matrix \
  --image "$image" \
  --inspect-image \
  --execute \
  "$@"
