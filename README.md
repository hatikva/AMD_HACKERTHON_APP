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
- `FACTUAL_KNOWLEDGE`: Fireworks Kimi alias `kimi-k2p7-code`, fallback Fireworks Minimax alias `minimax-m3`, `256` completion tokens.
- `LOGICAL_DEDUCTIVE_REASONING`: Fireworks Kimi alias `kimi-k2p7-code`, fallback Fireworks Minimax alias `minimax-m3`, `256` completion tokens.
- `MATHEMATICAL_REASONING`: Fireworks Kimi alias `kimi-k2p7-code`, fallback local Ollama `nemotron-3-nano:4b`, `400` completion tokens.
- `NAMED_ENTITY_RECOGNITION`: local Ollama `nemotron-3-nano:4b`, fallback Fireworks Kimi alias `kimi-k2p7-code`, `1000` completion tokens.
- `SENTIMENT_CLASSIFICATION`: Fireworks Kimi alias `kimi-k2p7-code`, fallback Fireworks Minimax alias `minimax-m3`, `256` completion tokens.
- `TEXT_SUMMARISATION`: local Ollama `nemotron-3-nano:4b`, fallback Fireworks Kimi alias `kimi-k2p7-code`, `1000` completion tokens.

Classification is local-first with bundled `nemotron-3-nano:4b`: it retries once locally, then falls back to Fireworks Kimi for a third classification attempt.

## Scheduler

Version 7 defaults to `post_classification_parallel` scheduling:

1. Classify and route every task serially with the bundled local model.
2. After classification completes, start answer generation for every task.
3. Fireworks-owned answer tasks run with bounded remote concurrency while local-answer tasks drain serially.

The deferred local queue contains exactly:

```text
CODE_DEBUGGING
NAMED_ENTITY_RECOGNITION
TEXT_SUMMARISATION
```

Fireworks requests may overlap local answering, but not classification. No two local Nemotron generations run concurrently. The older `streaming_remote` scheduler remains available only by explicitly setting `VERSION7_SCHEDULER_MODE=streaming_remote`.

## Answer Prompt Policy

Answer wrappers are fixed constants in `src/amd_hackathon_app/version7.py`. They are prepended to the single user message as:

```text
<category wrapper>

Task:
<official prompt>
```

They are not system prompts.

Final wrapper policy:

- `FACTUAL_KNOWLEDGE` Fireworks answers use the fixed factual wrapper.
- Other primary Fireworks categories use the raw official prompt.
- Local Ollama answer categories use their fixed category wrappers.
- Fallback answer calls keep the same category policy. For example, `FACTUAL_KNOWLEDGE` fallback to Minimax keeps the factual wrapper, and local-primary categories that fall back to Fireworks keep their category wrapper.
- Classifier prompts are separate and do not use answer wrappers.

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

Latest source verification on 2026-07-14:

```text
unit tests: 68 passed via PYTHONPATH=src python3 -m unittest discover -s tests
json policy: docs/algorithm.json validates with python3 -m json.tool
diff hygiene: git diff --check passed
final policy report: docs/VERSION7_MODE1_EXPERIMENT_REPORT.md
```

## Demo UI

The demo UI is separate from the official judging runtime. It is a review page for standard-like samples with expected answers, not the submission entrypoint.

Open the static demo page locally:

```bash
python3 -m http.server 8087 --directory demo
```

Then visit:

```text
http://127.0.0.1:8087/
```

Demo behavior:

- Uses two sample tasks per category from `benchmarks/categories/version6_shadow_category_benchmarks_v1.json`.
- Requires demo uploads to include `task_id`, `prompt`, `category`, and `expected_answer`.
- Rejects uploaded demo tasks that do not include expected answers.
- Shows per-task results, category coverage, and estimated prompt/completion token totals.
- Includes a clear-results control for fresh review runs.

Credential boundary:

- Browser demo code must not read, request, display, upload, or persist `FIREWORKS_API_KEY`.
- When the demo is connected to real model execution, the Python server/runtime loads credentials from server-side environment variables or repo `.env`.
- The judged production container still has no `.env` baked into the image and receives credentials only at runtime.

## Publication State

Current public image reference:

```text
ghcr.io/hatikva/amd-hackathon-app:version7-production-429c37b
```

Status: accessible. Anonymous pull from a clean Docker/Podman auth context succeeded on 2026-07-14 and resolved image config `sha256:868de9991a985a2993fa794cbf34213869483250c2d61dc72d4506c4b1fda729`.

This public tag is the previously verified image. The final policy in the current source tree requires a new image build and immutable tag before submission.

Pull the public image:

```bash
docker pull ghcr.io/hatikva/amd-hackathon-app:version7-production-429c37b
```

Run it with official input and output mounts:

```bash
docker run --rm \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e FIREWORKS_BASE_URL="$FIREWORKS_BASE_URL" \
  -e ALLOWED_MODELS="$ALLOWED_MODELS" \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  ghcr.io/hatikva/amd-hackathon-app:version7-production-429c37b
```

Verification recorded on 2026-07-14:

```text
graph ingestion: refreshed codebase-memory index for /home/user/repos/Hatikva/AMD_HACKERTHON_APP
unit tests: 68 passed via PYTHONPATH=src python3 -m unittest discover -s tests
public pull: passed with fresh DOCKER_CONFIG and REGISTRY_AUTH_FILE
image verification: scripts/verify-version7-image.sh passed
compressed image size: 3,038,200,608 bytes
constrained container smoke: passed under --memory=4g --cpus=2 with a fake Fireworks-compatible endpoint
smoke output: [{"task_id":"factual-smoke","answer":"Paris"}]
```

## Final Policy

The final policy is documented in `docs/VERSION7_MODE1_EXPERIMENT_REPORT.md`. It promotes the `post_classification_parallel` scheduler, 256-token caps for factual/logical/sentiment categories, local wrappers, targeted factual Fireworks wrapping, and fallback inheritance of the category prompt policy.
