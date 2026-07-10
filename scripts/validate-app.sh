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
python3 -m py_compile src/amd_hackathon_app/ui.py
python3 -m py_compile src/amd_hackathon_app/benchmarks.py
bash -n scripts/benchmark-version-candidates.sh
python3 -m amd_hackathon_app.cli validate-category-benchmark >"$tmp_root/category-benchmark.json"
python3 -m amd_hackathon_app.cli benchmark-categories \
  --provider mock \
  --output "$tmp_root/mock-category-qualification.json" >"$tmp_root/mock-category-qualification.stdout.json"

grep -q 'Most Innovative Routing System' README.md
grep -q 'Work Jurisdiction' README.md
grep -q 'FIREWORKS_BASE_URL' README.md
grep -q 'ALLOWED_MODELS' README.md
grep -q 'Local demo inference uses Ollama, not Lemonade' README.md
grep -q 'Version 5 local-first execution is blocked' README.md
grep -q 'version5-category-benchmark-v2' README.md
grep -q 'docs/algorithm.json' README.md

grep -q 'ALLOWED_MODELS' .env.example
grep -q 'qwen2.5-coder:3b' .env.example
grep -q 'LLAMA_MODEL_PATH' .env.example
grep -q 'FIREWORKS_BASE_URL' src/amd_hackathon_app/pipeline.py
grep -q 'ALLOWED_MODELS is required for Fireworks execution' src/amd_hackathon_app/pipeline.py
grep -q 'DEMO_LOCAL_MODEL_EXECUTION' src/amd_hackathon_app/pipeline.py
grep -q 'LlamaCppProvider' src/amd_hackathon_app/pipeline.py
grep -q 'ThreadingHTTPServer' src/amd_hackathon_app/ui.py
grep -q 'version3' web/app.js
grep -q 'analytics-grid' web/styles.css

grep -q 'no bundled model weights' docs/concept.json
grep -q 'Work Jurisdiction Routing' docs/algorithm.json
grep -q 'llama.cpp' docs/version5-local-first-candidate.json
grep -q 'version5-category-benchmark-v2' docs/version5-local-first-candidate.json
grep -q 'ALLOWED_MODELS' docs/allowed-models.json
grep -q '/input/tasks.json' docs/repo-structure.json
grep -q 'version5_local_category_benchmarks_v2.json' benchmarks/categories/README.md
grep -q 'version5_local_category_benchmarks_v2.json' docs/BENCHMARK_STATUS.md

grep -q 'python:3.12-slim' Dockerfile.submission
grep -q 'python:3.12-slim' Dockerfile.ui
grep -q 'amd-router' Dockerfile.ui
grep -q 'network_mode: host' compose.ui.yml
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

python3 - "$tmp_root/category-benchmark.json" "$tmp_root/mock-category-qualification.json" <<'PY'
import json
import sys
from pathlib import Path

benchmark = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
qualification = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert benchmark["benchmark_suite"] == "version5-category-benchmark-v2"
assert benchmark["task_count"] == 40
assert qualification["benchmark_suite"] == "version5-category-benchmark-v2"
assert qualification["authorization_registry_mutated"] is False
assert len(qualification["results"]) == 40
assert all("evaluation" not in row["model_visible_task"] for row in qualification["results"])
PY

echo "app validation passed"
