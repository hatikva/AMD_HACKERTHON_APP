# AMD Hackathon App

Track 1 hybrid token-efficient routing agent for local Lemonade inference plus Fireworks API inference.

The implementation follows the planning repo `hatikva/AMD_HACKERTHON_IMPLEMENTATION_PLAN`. Run the planning audit gate before changing direction:

```bash
cd ../AMD_HACKERTHON_IMPLEMENTATION_PLAN
python3 tools/validate-planning-repo.py
```

## Current Standing

This repository contains the first vertical-slice scaffold:

- CPU-only Lemonade Compose service pinned to `ghcr.io/lemonade-sdk/lemonade-server:v9.1.3`
- provider-neutral routing pipeline
- MDR context packet generation
- profile-based accuracy-first routing
- local Lemonade and Fireworks provider boundaries
- mock provider for offline pipeline verification
- compact benchmark scenarios
- audit/result records under ignored `runs/` and `benchmarks/results/`

Unfinished runtime work is tracked in `audit/pipeline.json`. Items that cannot be completed in the current environment remain queued with a command and next action; they are not treated as unmanaged blockers.

Audit receipt:

- `audit/receipts/2026-06-25-first-vertical-slice.receipt.json`
- `audit/receipts/2026-06-25-lemonade-runtime-verified.receipt.json`
- `audit/receipts/2026-06-25-candidate-model-acquisition.receipt.json`
- `audit/receipts/2026-06-25-profile-benchmark-evidence.receipt.json`

## Daily Commands

Create a local environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Run the offline vertical slice:

```bash
python -m amd_hackathon_app.cli run-scenario --scenario classification-basic --provider mock
```

Run unit tests:

```bash
python -m unittest discover -s tests
```

Run the app audit gate:

```bash
scripts/validate-app.sh
```

Show or advance the implementation pipeline:

```bash
scripts/advance-pipeline.sh show
scripts/advance-pipeline.sh ollama-port-handoff
scripts/advance-pipeline.sh lemonade-runtime-start
scripts/advance-pipeline.sh lemonade-runtime-verify
scripts/advance-pipeline.sh candidate-model-acquisition
```

Inspect environment:

```bash
python -m amd_hackathon_app.cli preflight
```

Start Lemonade development service:

```bash
scripts/setup-lemonade.sh
```

Restart an already-configured Lemonade pod quickly:

```bash
podman pod start pod_amd_hackerthon_app
```

`pod_amd_hackerthon_app` contains the `amd-hackathon-lemonade` container. Stopping that pod stops the Lemonade server, and starting that pod starts the existing Lemonade container again. Prefer `scripts/advance-pipeline.sh lemonade-runtime-start` for normal project work because it stops Ollama first, runs Compose, rebuilds if needed, starts Lemonade, and waits for `127.0.0.1:13305` to respond. Use `podman pod start pod_amd_hackerthon_app` only when the container is already configured and a quick restart is enough.

Verify Lemonade:

```bash
scripts/verify-lemonade.sh
```

Benchmark routing profiles:

```bash
scripts/benchmark-profiles.sh
```

## Routing Rule

The router is accuracy-first:

- route to Fireworks when task difficulty exceeds the active local threshold;
- route to Fireworks when router confidence is below the active profile minimum;
- route to Fireworks when decisive context cannot fit in the local MDR budget;
- escalate when local validation fails;
- optimize token and cost only after a model tier is accurate enough.

## Development Volumes

`compose.dev.yml` defines named volumes:

- `lemonade-cache`: Hugging Face/model cache for development downloads.
- `lemonade-llama`: Lemonade llama.cpp backend binaries.
- `lemonade-recipe`: Lemonade recipe/config/cache state.

These volumes are development caches. They are not part of a Docker image and must not be assumed present for scoring. The CPU defaults file is mounted explicitly to `/root/.cache/lemonade/config.json` so the recipe volume does not hide the required CPU configuration.
