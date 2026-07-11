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
[
  {
    "task_id": "validation-task",
    "prompt": "Classify sentiment: the routing demo is ready."
  }
]
JSON

python3 -m amd_hackathon_app.cli run-submission \
  --input "$tmp_root/input/tasks.json" \
  --output "$tmp_root/output/results.json" \
  --provider mock >"$tmp_root/batch.json"

python3 -m py_compile scripts/model-acquisition.py scripts/show-pipeline.py
python3 -m py_compile src/amd_hackathon_app/ui.py
python3 -m py_compile src/amd_hackathon_app/benchmarks.py
python3 -m py_compile src/amd_hackathon_app/analytics.py
bash -n scripts/benchmark-version-candidates.sh
python3 -m amd_hackathon_app.cli validate-category-benchmark >"$tmp_root/category-benchmark.json"
python3 -m amd_hackathon_app.cli build-version5-analytics \
  --results-dir qualification/results \
  --output "$tmp_root/version5_authority_analytics.json" >"$tmp_root/version5_authority_analytics.stdout.json"
python3 -m amd_hackathon_app.cli build-version6-analytics \
  --results-dir qualification/results \
  --output "$tmp_root/version6_submission_analytics.json" >"$tmp_root/version6_submission_analytics.stdout.json"
python3 -m amd_hackathon_app.cli benchmark-categories \
  --provider mock \
  --output "$tmp_root/mock-category-qualification.json" >"$tmp_root/mock-category-qualification.stdout.json"

grep -q 'Version 6 is the confirmed final-stage runtime' README.md
grep -q 'version6-staging' README.md
grep -q 'version6-production' README.md
grep -q 'version6-analytics-ui' README.md
grep -q 'analytics only' README.md
grep -q 'FIREWORKS_BASE_URL' README.md
grep -q 'ALLOWED_MODELS' README.md
grep -q '/input/tasks.json' README.md
grep -q '/output/results.json' README.md

grep -q 'ALLOWED_MODELS' .env.example
grep -q 'qwen2.5-coder:3b' .env.example
grep -q 'OLLAMA_MODEL_NAME' .env.example
grep -q 'LLAMA_MODEL_PATH' .env.example
grep -q 'FIREWORKS_BASE_URL' src/amd_hackathon_app/pipeline.py
grep -q 'ALLOWED_MODELS is required for Fireworks execution' src/amd_hackathon_app/pipeline.py
grep -q 'DEMO_LOCAL_MODEL_EXECUTION' src/amd_hackathon_app/pipeline.py
grep -q 'LlamaCppProvider' src/amd_hackathon_app/pipeline.py
grep -q 'OllamaLocalProvider' src/amd_hackathon_app/pipeline.py
grep -q 'version6-production' src/amd_hackathon_app/pipeline.py
grep -q 'STAGING_INFERENCE_BASE_URL' src/amd_hackathon_app/pipeline.py
grep -q 'ThreadingHTTPServer' src/amd_hackathon_app/ui.py
grep -q 'METHOD_NOT_ALLOWED' src/amd_hackathon_app/ui.py
grep -q 'Version 6 Analytics' web/index.html
grep -q 'api/version6-analytics' web/app.js
if grep -q 'api/run\|taskInput\|runButton' web/app.js web/index.html; then
  echo "Version 6 analytics UI must not expose live task execution controls" >&2
  exit 1
fi

grep -q 'no bundled model weights' docs/concept.json
grep -q 'Work Jurisdiction Routing' docs/algorithm.json
grep -q 'llama.cpp' docs/version5-local-first-candidate.json
grep -q 'version5-category-benchmark-v2' docs/version5-local-first-candidate.json
grep -q 'ALLOWED_MODELS' docs/allowed-models.json
grep -q '/input/tasks.json' docs/repo-structure.json
grep -q 'version5_local_category_benchmarks_v2.json' benchmarks/categories/README.md
grep -q 'version5_local_category_benchmarks_v2.json' docs/BENCHMARK_STATUS.md
grep -q 'Categorization Risk' docs/CATEGORIZATION_RISK.md

grep -q 'python:3.12-slim' Dockerfile.submission
grep -q 'python:3.12-slim' Dockerfile.ui
grep -q 'amd-router' Dockerfile.ui
grep -q 'network_mode: host' compose.ui.yml
grep -q 'amd-router' Dockerfile.submission
grep -q 'llama.cpp local-first candidate' Dockerfile.version5
grep -q 'Version 5 Ollama Final Runtime' Dockerfile.version5-ollama
grep -q 'version5-ollama' Dockerfile.version5-ollama
grep -q 'version6-staging' Dockerfile.version6
grep -q 'version6-production' Dockerfile.version6
grep -q 'test ! -e /app/web' Dockerfile.version6
grep -q 'Version 6 Analytics UI' Dockerfile.version6-ui
if grep -q 'lemonade-server' Dockerfile.submission; then
  echo "submission Dockerfile must not depend on Lemonade" >&2
  exit 1
fi

python3 - "$tmp_root/output/results.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert isinstance(payload, list)
assert payload == [{"answer": '{"label":"neutral","confidence":0.74}', "task_id": "validation-task"}]
assert set(payload[0]) == {"task_id", "answer"}
PY

python3 - "$tmp_root/category-benchmark.json" "$tmp_root/mock-category-qualification.json" "$tmp_root/version5_authority_analytics.json" "$tmp_root/version6_submission_analytics.json" <<'PY'
import json
import sys
from pathlib import Path

benchmark = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
qualification = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
analytics = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
version6 = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
assert benchmark["benchmark_suite"] == "version5-category-benchmark-v2"
assert benchmark["task_count"] == 40
assert qualification["benchmark_suite"] == "version5-category-benchmark-v2"
assert qualification["authorization_registry_mutated"] is False
assert len(qualification["results"]) == 40
assert all("evaluation" not in row["model_visible_task"] for row in qualification["results"])
assert all(set(row["model_visible_task"]) == {"task_id", "prompt"} for row in qualification["results"])
assert qualification["production_path_used"] is True
assert analytics["schema"] == "amd_hackathon.version5_authority_analytics.v1"
assert analytics["authorization_registry_mutated"] is False
assert analytics["local_jurisdictions_promoted"] == []
assert analytics["categorization_evaluation"]["official_shape_valid"] is True
assert version6["schema"] == "amd_hackathon.version6_submission_analytics.v1"
assert version6["submission_compliance"]["analytics_ui"]["task_input_form"] is False
assert version6["submission_compliance"]["analytics_ui"]["live_execution_endpoint"] is False
assert version6["deduced_analytics"]["fireworks_called"] is False
PY

echo "app validation passed"
