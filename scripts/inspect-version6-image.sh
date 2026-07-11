#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:?usage: scripts/inspect-version6-image.sh IMAGE}"
DOCKER="${DOCKER:-docker}"
LIMIT_BYTES="${VERSION6_IMAGE_LIMIT_BYTES:-10000000000}"
case "$IMAGE" in
  *staging*) EXPECTED_POLICY_MODE="${VERSION6_EXPECTED_POLICY_MODE:-staging}" ;;
  *) EXPECTED_POLICY_MODE="${VERSION6_EXPECTED_POLICY_MODE:-production}" ;;
esac

compressed_size="$("$DOCKER" save "$IMAGE" | gzip -c | wc -c)"
echo "compressed_image_bytes=$compressed_size"
if [ "$compressed_size" -ge "$LIMIT_BYTES" ]; then
  echo "compressed image size $compressed_size exceeds limit $LIMIT_BYTES" >&2
  exit 1
fi

"$DOCKER" run --rm --entrypoint sh "$IMAGE" -c '
set -eu
compact_policy_present=false
policy_schema_valid=false
policy_mode_matches_image=false
raw_benchmark_evidence_absent=false
expected_answers_absent=false
evaluator_metadata_absent=false
secrets_absent=false
production_provider_boundary_valid=false

for forbidden in /app/web /app/benchmarks /app/qualification /app/.env /app/data/app.sqlite3; do
  if [ -e "$forbidden" ]; then
    echo "forbidden artifact present: $forbidden" >&2
    exit 1
  fi
done
raw_benchmark_evidence_absent=true
if find /app -type f | grep -Ei "(accepted|fixture|grading|rubric|reference_solution|expected)" >/tmp/forbidden-files.txt; then
  cat /tmp/forbidden-files.txt >&2
  exit 1
fi
expected_answers_absent=true
evaluator_metadata_absent=true
if find /app -type f \( -name ".env" -o -name "*.env" -o -name "*secret*" -o -name "*credential*" \) | grep . >/tmp/secret-files.txt; then
  cat /tmp/secret-files.txt >&2
  exit 1
fi
secrets_absent=true
test -x /usr/local/bin/ollama
test -s /app/ollama-models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970
python - "$0" <<PY
import json
import sys
from pathlib import Path

expected_mode = sys.argv[1]
paths = {
    "production": Path("/app/src/amd_hackathon_app/authorization/version6_routing_policy.json"),
    "staging": Path("/app/src/amd_hackathon_app/authorization/version6_staging_authorizations.json"),
}
path = paths[expected_mode]
assert path.is_file() and path.stat().st_size > 0, path
payload = json.loads(path.read_text(encoding="utf-8"))
required = {
    "schema",
    "policy_id",
    "generated_at",
    "policy_mode",
    "source_calibration_artifact_hash",
    "threshold_config_hash",
    "official_fireworks_token_score_status",
    "category_routes",
    "work_scope_routes",
    "fallback_routes",
    "failed_or_denied_routes",
    "allowed_model_source",
    "provider_boundary",
}
assert payload.get("schema") == "amd_hackathon.version6.routing_policy.v1", payload.get("schema")
assert not (required - set(payload)), required - set(payload)
assert payload["policy_mode"] == expected_mode, payload["policy_mode"]
if expected_mode == "production":
    assert "ollama" not in payload["provider_boundary"].lower(), payload["provider_boundary"]
provider_boundary_valid = expected_mode != "production" or "fireworks" in payload["provider_boundary"].lower()
print("compact_policy_present=true")
print("policy_schema_valid=true")
print("policy_mode_matches_image=true")
print("raw_benchmark_evidence_absent=true")
print("expected_answers_absent=true")
print("evaluator_metadata_absent=true")
print("secrets_absent=true")
print(f"production_provider_boundary_valid={str(provider_boundary_valid).lower()}")
PY
' "$EXPECTED_POLICY_MODE"

echo "version6_image_inspection=passed"
