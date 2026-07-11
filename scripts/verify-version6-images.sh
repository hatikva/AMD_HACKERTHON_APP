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
cat > "$tmpdir/mock-production-policy.json" <<'JSON'
{
  "allowed_model_source": "test",
  "category_routes": {},
  "failed_or_denied_routes": {},
  "fallback_routes": {
    "default": {
      "authorization_status": "fallback",
      "fallback_policy": "default",
      "required_gates_passed": true,
      "runner_up_model": "mock-model",
      "runner_up_provider": "mock",
      "selected_model": "mock-model",
      "selected_provider": "mock"
    }
  },
  "generated_at": "2026-07-11T00:00:00Z",
  "official_fireworks_token_score_status": "NOT_MEASURED_TEST",
  "policy_id": "version6-production-policy-smoke",
  "policy_mode": "production",
  "provider_boundary": "test_mock_only",
  "schema": "amd_hackathon.version6.routing_policy.v1",
  "source_calibration_artifact_hash": "sha256:test",
  "threshold_config_hash": "sha256:test",
  "work_scope_routes": {}
}
JSON

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
    -e VERSION6_PRODUCTION_POLICY_PATH=/policy/mock-production-policy.json \
    -e AMD_POLICY_TEST_ALLOW_MOCK=1 \
    -v "$tmpdir/input:/input:ro" \
    -v "$tmpdir/mock-production-policy.json:/policy/mock-production-policy.json:ro" \
    -v "$tmpdir/output:/output" \
    "$PRODUCTION_IMAGE"
fi

python3 - <<PY
import json
from pathlib import Path
path = Path("$tmpdir/output/results.json")
rows = json.loads(path.read_text())
assert isinstance(rows, list), rows
assert rows and set(rows[0]) == {"task_id", "answer"}, rows
encoded = json.dumps(rows)
for forbidden in ["policy", "selected_model", "selected_provider", "token", "mock-model"]:
    assert forbidden not in encoded, encoded
print("runtime_policy_smoke_passed=true")
print("official_output_contract_passed=true")
print(json.dumps(rows, indent=2))
PY

echo "image_push_allowed=true"
