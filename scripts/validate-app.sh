#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=src

python3 -m unittest discover -s tests
python3 -m amd_hackathon_app.cli preflight >/tmp/amd-hackathon-app-preflight.json
python3 -m amd_hackathon_app.cli run-scenario \
  --scenario classification-basic \
  --provider mock \
  --run-dir /tmp/amd-hackathon-app-runs >/tmp/amd-hackathon-app-vertical-slice.json
python3 scripts/show-pipeline.py >/tmp/amd-hackathon-app-pipeline.txt
docker compose -f compose.dev.yml config >/tmp/amd-hackathon-app-compose.yml

grep -q '127.0.0.1:13305:13305' /tmp/amd-hackathon-app-compose.yml
grep -q 'ghcr.io/lemonade-sdk/lemonade-server:v9.1.3' containers/lemonade/Dockerfile
grep -q '"backend": "cpu"' containers/lemonade/defaults.json
grep -q 'Unfinished work remains in the implementation pipeline' /tmp/amd-hackathon-app-pipeline.txt

echo "app validation passed"
