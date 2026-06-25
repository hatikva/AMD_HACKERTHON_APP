#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

stage="${1:-}"

case "$stage" in
  show|"")
    scripts/show-pipeline.py
    ;;
  planning-audit-gate)
    (cd ../AMD_HACKERTHON_IMPLEMENTATION_PLAN && python3 tools/validate-planning-repo.py)
    ;;
  offline-router-vertical-slice)
    scripts/validate-app.sh
    ;;
  ollama-port-handoff)
    scripts/stop-ollama.sh
    ;;
  lemonade-runtime-start)
    scripts/setup-lemonade.sh
    ;;
  lemonade-runtime-verify)
    scripts/verify-lemonade.sh
    ;;
  candidate-model-acquisition)
    scripts/pull-candidate-models.sh
    ;;
  ollama-gguf-import-audit)
    python3 scripts/audit-ollama-gguf.py
    ;;
  profile-benchmark-evidence)
    PROVIDER_OVERRIDE="${PROVIDER_OVERRIDE:-local}" scripts/benchmark-profiles.sh
    ;;
  *)
    echo "unknown pipeline stage: $stage" >&2
    echo "run scripts/advance-pipeline.sh show" >&2
    exit 2
    ;;
esac
