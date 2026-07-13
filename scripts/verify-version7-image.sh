#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-amd-hackathon:version7-production}"
DOCKER="${DOCKER:-docker}"

compressed_bytes="$($DOCKER image inspect "$IMAGE" --format '{{.Size}}')"
if [ "$compressed_bytes" -ge 10000000000 ]; then
  echo "compressed_image_size_too_large=$compressed_bytes" >&2
  exit 1
fi

"$DOCKER" run --rm --entrypoint /bin/sh "$IMAGE" -c '
set -eu
command -v ollama >/dev/null
test -s /app/ollama-models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970
test ! -e /app/benchmarks
test ! -e /app/qualification
test ! -e /app/.env
test ! -e /app/src/amd_hackathon_app/ui.py
test ! -e /app/src/amd_hackathon_app/analytics.py
grep -R "kimi-k2p7-code" -n /usr/local/lib/python*/site-packages/amd_hackathon_app/version7.py >/dev/null
grep -R "minimax-m3" -n /usr/local/lib/python*/site-packages/amd_hackathon_app/version7.py >/dev/null
'

tmpdir="$(mktemp -d /tmp/version7-verify.XXXXXX)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT
mkdir -p "$tmpdir/input" "$tmpdir/output"
printf '%s\n' '[{"task_id":"bad","prompt":"bad"}]' > "$tmpdir/input/tasks.json"

if "$DOCKER" run --rm \
  -e ALLOWED_MODELS=accounts/fireworks/models/minimax-m3 \
  -e FIREWORKS_API_KEY=test \
  -e FIREWORKS_BASE_URL=http://127.0.0.1:9 \
  -v "$tmpdir/input:/input:ro" \
  -v "$tmpdir/output:/output" \
  "$IMAGE"; then
  echo "missing_kimi_allowed_model_should_fail=true" >&2
  exit 1
fi

if "$DOCKER" run --rm \
  -e ALLOWED_MODELS=accounts/fireworks/models/kimi-k2p7-code \
  -e FIREWORKS_API_KEY=test \
  -e FIREWORKS_BASE_URL=http://127.0.0.1:9 \
  -v "$tmpdir/input:/input:ro" \
  -v "$tmpdir/output:/output" \
  "$IMAGE"; then
  echo "missing_minimax_allowed_model_should_fail=true" >&2
  exit 1
fi

echo "version7_image_inspection_passed=true"
echo "compressed_image_size=$compressed_bytes"
