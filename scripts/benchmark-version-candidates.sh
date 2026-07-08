#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=src

out_dir="${1:-benchmarks/results}"
mkdir -p "$out_dir"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
result_path="$out_dir/version-candidates-$timestamp.jsonl"

python3 -m amd_hackathon_app.cli run-scenario \
  --scenario classification-basic \
  --provider mock >>"$result_path"

if [[ -n "${FIREWORKS_API_KEY:-}" && -n "${FIREWORKS_BASE_URL:-}" && -n "${ALLOWED_MODELS:-}" ]]; then
  python3 -m amd_hackathon_app.cli run-scenario \
    --scenario classification-basic \
    --provider version5 >>"$result_path"
else
  printf '{"candidate_version":"version_5","status":"blocked","reason":"FIREWORKS_API_KEY, FIREWORKS_BASE_URL, and ALLOWED_MODELS are required until a local GGUF model is certified"}\n' >>"$result_path"
fi

printf '%s\n' "$result_path"
