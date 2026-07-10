#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:-amd-hackathon-version5:ollama}"
LIMIT_BYTES="${VERSION5_IMAGE_LIMIT_BYTES:-10000000000}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER="${DOCKER:-docker}"

cd "$ROOT_DIR"

scripts/stage-version5-ollama-runtime.sh >/dev/null
"$DOCKER" build -f Dockerfile.version5-ollama -t "$IMAGE" .

compressed_size="$("$DOCKER" save "$IMAGE" | gzip -c | wc -c)"
echo "compressed_image_bytes=$compressed_size"
if [ "$compressed_size" -ge "$LIMIT_BYTES" ]; then
  echo "compressed image size $compressed_size exceeds limit $LIMIT_BYTES" >&2
  exit 1
fi

tmpdir="$(mktemp -d /tmp/version5-ollama-verify.XXXXXX)"
container_name="version5-ollama-verify-$$"
cleanup() {
  "$DOCKER" rm "$container_name" >/dev/null 2>&1 || true
  rm -rf "$tmpdir"
}
trap cleanup EXIT

mkdir -p "$tmpdir/input" "$tmpdir/output"
printf '%s\n' '[{"task_id":"smoke_math","prompt":"Answer with only the number: what is 2 + 2?"}]' > "$tmpdir/input/tasks.json"

"$DOCKER" run \
  --name "$container_name" \
  --memory=4g \
  --cpus=2 \
  -v "$tmpdir/input:/input:ro" \
  -v "$tmpdir/output:/output" \
  "$IMAGE"

"$DOCKER" inspect "$container_name" --format 'oom_killed={{.State.OOMKilled}} exit_code={{.State.ExitCode}}'
cat "$tmpdir/output/results.json"
