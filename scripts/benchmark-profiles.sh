#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p benchmarks/results
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="benchmarks/results/profile-benchmark-${STAMP}.jsonl"

for scenario in classification-basic json-extraction-basic reasoning-escalation-boundary; do
  python3 -m amd_hackathon_app.cli run-scenario \
    --scenario "$scenario" \
    --provider "${PROVIDER_OVERRIDE:-mock}" >> "$OUT"
done

echo "wrote $OUT"
