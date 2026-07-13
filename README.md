# AMD Hackathon Track 1 Version 7 Runtime

This repository is the official application repository for the AMD Developer Hackathon ACT II Track 1 submission runtime.

Version 7 is the current submission candidate. It is a batch-only container runtime that reads `/input/tasks.json`, writes `/output/results.json`, and exits. It has no UI, no public HTTP server, no interactive input, and no manual trigger.

Version 6 remains preserved in `Dockerfile.version6` as historical fallback evidence only.

## Runtime Contract

Input:

```text
/input/tasks.json
```

The input must be a top-level JSON array. Each task must contain non-empty string fields:

```json
{"task_id": "task-1", "prompt": "Official task prompt"}
```

Output:

```text
/output/results.json
```

The output is a top-level JSON array preserving input order. Each item contains exactly:

```json
{"task_id": "task-1", "answer": "Generated answer"}
```

Internal audit records may be written under `/output/audit`, but they are not part of the official result file.

## Version 7 Routing

All tasks are classified locally with bundled `nemotron-3-nano:4b`. The classifier is separate from answer generation and returns exactly one canonical category.

Locked primary/fallback policy:

- `CODE_DEBUGGING`: local Ollama `nemotron-3-nano:4b`, fallback Fireworks Kimi alias `kimi-k2p7-code`, `1000` completion tokens.
- `CODE_GENERATION`: Fireworks Kimi alias `kimi-k2p7-code`, fallback local Ollama `nemotron-3-nano:4b`, `1000` completion tokens.
- `FACTUAL_KNOWLEDGE`: Fireworks Kimi alias `kimi-k2p7-code`, fallback Fireworks Minimax alias `minimax-m3`, `64` completion tokens.
- `LOGICAL_DEDUCTIVE_REASONING`: Fireworks Kimi alias `kimi-k2p7-code`, fallback Fireworks Minimax alias `minimax-m3`, `64` completion tokens.
- `MATHEMATICAL_REASONING`: Fireworks Kimi alias `kimi-k2p7-code`, fallback local Ollama `nemotron-3-nano:4b`, `400` completion tokens.
- `NAMED_ENTITY_RECOGNITION`: local Ollama `nemotron-3-nano:4b`, fallback Fireworks Kimi alias `kimi-k2p7-code`, `1000` completion tokens.
- `SENTIMENT_CLASSIFICATION`: Fireworks Kimi alias `kimi-k2p7-code`, fallback Fireworks Minimax alias `minimax-m3`, `64` completion tokens.
- `TEXT_SUMMARISATION`: local Ollama `nemotron-3-nano:4b`, fallback Fireworks Kimi alias `kimi-k2p7-code`, `1000` completion tokens.

Classification is local-first with bundled `nemotron-3-nano:4b`: it retries once locally, then falls back to Fireworks Kimi for a third classification attempt.

## Scheduler

Version 7 uses two logical phases:

1. Serial local classification. Fireworks-owned tasks are dispatched immediately after classification with bounded remote concurrency.
2. After all tasks are classified, the combined local queue drains serially.

The deferred local queue contains exactly:

```text
CODE_DEBUGGING
NAMED_ENTITY_RECOGNITION
TEXT_SUMMARISATION
```

Fireworks requests may overlap later classification and post-barrier local answering. No two local Nemotron generations run concurrently.

## Fireworks Environment

The evaluator supplies:

```text
FIREWORKS_API_KEY
FIREWORKS_BASE_URL
ALLOWED_MODELS
```

`ALLOWED_MODELS` is parsed at runtime. The runtime requires exactly one allowed model resource whose final resource-name component is `kimi-k2p7-code`, and exactly one whose final component is `minimax-m3`.

## Build

Build the official submission image:

```bash
docker build -f Dockerfile.submission -t amd-hackathon:version7-production .
```

Equivalent explicit Version 7 build:

```bash
docker build -f Dockerfile.version7 --target version7-production -t amd-hackathon:version7-production .
```

Build for the judging architecture:

```bash
docker buildx build --platform linux/amd64 \
  -f Dockerfile.submission \
  -t ghcr.io/hatikva/amd-hackathon-app:version7-production-<short-commit> .
```

## Run

```bash
docker run --rm \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e FIREWORKS_BASE_URL="$FIREWORKS_BASE_URL" \
  -e ALLOWED_MODELS="$ALLOWED_MODELS" \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  amd-hackathon:version7-production
```

## Verification

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Inspect the built image:

```bash
scripts/verify-version7-image.sh amd-hackathon:version7-production
```

Latest local verification:

```text
app commit: f1dfc86e9d4c83ac835b3f383874df062ffdf52d
image id: b273c4f9e73d25885118603e1d9116f07f9f11a057531e31c068ca5aeb6108cd
local repo digest: sha256:7762542e1d3d1bca618dd193b229f48adaa33aa1e19ecf99241d28e810b9ba64
architecture: linux/amd64
compressed size: 3,038,179,852 bytes
unit tests: 61 passed
mixed eight-category smoke: passed, 210 seconds
deferred local queue smoke: passed, 142 seconds
```

## Publication State

Intended public image reference:

```text
ghcr.io/hatikva/amd-hackathon-app:version7-production-f1dfc86
```

Publication is currently blocked by GHCR permissions: `docker push` returns `403 Forbidden`. Do not submit the Version 7 image reference until the push succeeds and the tag is publicly pullable.
