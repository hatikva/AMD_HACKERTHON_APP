#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

mkdir -p benchmarks/results
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="benchmarks/results/profile-benchmark-${STAMP}.jsonl"

for profile in phi-nemotron-balanced phi-qwen-coder-balanced phi-fireworks-balanced; do
for scenario in classification-basic json-extraction-basic reasoning-escalation-boundary; do
  tmp_out="$(mktemp)"
  tmp_err="$(mktemp)"
  if python3 -m amd_hackathon_app.cli run-scenario \
    --scenario "$scenario" \
    --profile "$profile" >"$tmp_out" 2>"$tmp_err"; then
    cat "$tmp_out" >> "$OUT"
  else
    python3 - "$scenario" "$profile" "$tmp_err" >> "$OUT" <<'PY'
import json
import sys

scenario = sys.argv[1]
profile = sys.argv[2]
error_path = sys.argv[3]
error_text = open(error_path, encoding="utf-8").read()
print(json.dumps({
    "task_id": scenario,
    "profile_id": profile,
    "benchmark_status": "provider_failed",
    "error_tail": "\n".join(error_text.splitlines()[-20:]),
}, sort_keys=True))
PY
  fi
  rm -f "$tmp_out" "$tmp_err"
done
done

echo "wrote $OUT"
