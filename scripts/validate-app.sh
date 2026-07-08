#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=src

tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT

python3 -m unittest discover -s tests
python3 -m amd_hackathon_app.cli preflight >"$tmp_root/preflight.json"
python3 -m amd_hackathon_app.cli run-scenario \
  --scenario classification-basic \
  --provider mock \
  --run-dir "$tmp_root/runs" >"$tmp_root/vertical-slice.json"

mkdir -p "$tmp_root/input" "$tmp_root/output"
cat >"$tmp_root/input/tasks.json" <<'JSON'
{
  "tasks": [
    {
      "id": "validation-task",
      "prompt": "Classify sentiment: the routing demo is ready.",
      "task_family": "sentiment",
      "expected_format": "json"
    }
  ]
}
JSON

python3 -m amd_hackathon_app.cli run-tasks \
  --input "$tmp_root/input/tasks.json" \
  --output "$tmp_root/output/results.json" \
  --provider mock >"$tmp_root/batch.json"

python3 -m py_compile scripts/model-acquisition.py scripts/show-pipeline.py
bash -n scripts/benchmark-version-candidates.sh

grep -q 'Most Innovative Routing System' README.md
grep -q 'Work Jurisdiction' README.md
grep -q 'FIREWORKS_BASE_URL' README.md
grep -q 'ALLOWED_MODELS' README.md
grep -q 'Local demo inference uses Ollama, not Lemonade' README.md
grep -q 'Version 5 local-first execution is blocked' README.md
grep -q 'docs/algorithm.json' README.md

grep -q 'ALLOWED_MODELS' .env.example
grep -q 'qwen2.5-coder:3b' .env.example
grep -q 'LLAMA_MODEL_PATH' .env.example
grep -q 'FIREWORKS_BASE_URL' src/amd_hackathon_app/pipeline.py
grep -q 'ALLOWED_MODELS is required for Fireworks execution' src/amd_hackathon_app/pipeline.py
grep -q 'DEMO_LOCAL_MODEL_EXECUTION' src/amd_hackathon_app/pipeline.py
grep -q 'LlamaCppProvider' src/amd_hackathon_app/pipeline.py

grep -q 'no bundled model weights' docs/concept.json
grep -q 'Work Jurisdiction Routing' docs/algorithm.json
grep -q 'llama.cpp' docs/version5-local-first-candidate.json
grep -q 'ALLOWED_MODELS' docs/allowed-models.json
grep -q '/input/tasks.json' docs/repo-structure.json

grep -q 'python:3.12-slim' Dockerfile.submission
grep -q 'amd-router' Dockerfile.submission
grep -q 'llama.cpp local-first candidate' Dockerfile.version5
if grep -q 'lemonade-server' Dockerfile.submission; then
  echo "submission Dockerfile must not depend on Lemonade" >&2
  exit 1
fi

python3 - "$tmp_root/output/results.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["schema"] == "amd_hackathon.results.v3"
assert payload["results"][0]["work_jurisdiction"] in {"ANSWER_SCHEMA_SELECTION", "DEMO_LOCAL_MODEL_EXECUTION"}
assert payload["results"][0]["validation_result"]["passed"] is True
PY

echo "app validation passed"
