#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER="${DOCKER:-docker}"
STAGING_IMAGE="${1:-amd-hackathon:version6-staging}"
PRODUCTION_IMAGE="${2:-amd-hackathon:version6-production}"

cd "$ROOT_DIR"

scripts/stage-version5-ollama-runtime.sh >/dev/null
"$DOCKER" build -f Dockerfile.version6 --target version6-staging -t "$STAGING_IMAGE" .
"$DOCKER" build -f Dockerfile.version6 --target version6-production -t "$PRODUCTION_IMAGE" .

scripts/inspect-version6-image.sh "$STAGING_IMAGE"
scripts/inspect-version6-image.sh "$PRODUCTION_IMAGE"

tmpdir="$(mktemp -d /tmp/version6-verify.XXXXXX)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

mkdir -p "$tmpdir/input" "$tmpdir/output"
printf '%s\n' '[{"task_id":"smoke_math","prompt":"Answer with only the number: what is 2 + 2?"}]' > "$tmpdir/input/tasks.json"

if [ -n "${FIREWORKS_API_KEY:-}" ] && [ -n "${FIREWORKS_BASE_URL:-}" ] && [ -n "${ALLOWED_MODELS:-}" ]; then
  "$DOCKER" run --rm \
    --memory=4g \
    --cpus=2 \
    -e FIREWORKS_API_KEY \
    -e FIREWORKS_BASE_URL \
    -e ALLOWED_MODELS \
    -v "$tmpdir/input:/input:ro" \
    -v "$tmpdir/output:/output" \
    "$PRODUCTION_IMAGE"
else
  "$DOCKER" run --rm \
    --memory=4g \
    --cpus=2 \
    -v "$tmpdir/input:/input:ro" \
    -v "$tmpdir/output:/output" \
    "$PRODUCTION_IMAGE" \
    amd-router run-submission --input /input/tasks.json --output /output/results.json --provider version6-ollama
fi

python3 - <<PY
import json
from pathlib import Path
path = Path("$tmpdir/output/results.json")
rows = json.loads(path.read_text())
assert isinstance(rows, list), rows
assert rows and set(rows[0]) == {"task_id", "answer"}, rows
print(json.dumps(rows, indent=2))
PY
