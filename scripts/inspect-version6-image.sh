#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:?usage: scripts/inspect-version6-image.sh IMAGE}"
DOCKER="${DOCKER:-docker}"
LIMIT_BYTES="${VERSION6_IMAGE_LIMIT_BYTES:-10000000000}"

compressed_size="$("$DOCKER" save "$IMAGE" | gzip -c | wc -c)"
echo "compressed_image_bytes=$compressed_size"
if [ "$compressed_size" -ge "$LIMIT_BYTES" ]; then
  echo "compressed image size $compressed_size exceeds limit $LIMIT_BYTES" >&2
  exit 1
fi

"$DOCKER" run --rm --entrypoint sh "$IMAGE" -c '
set -eu
for forbidden in /app/web /app/benchmarks /app/qualification /app/.env /app/data/app.sqlite3; do
  if [ -e "$forbidden" ]; then
    echo "forbidden artifact present: $forbidden" >&2
    exit 1
  fi
done
find /app -type f | grep -Ei "(answer|accepted|fixture|grading|rubric|reference_solution|expected)" && exit 1 || true
test -x /usr/local/bin/ollama
test -s /app/ollama-models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970
'

echo "version6_image_inspection=passed"
