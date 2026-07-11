# AMD Hackathon Version 6 Submission Runtime

Version 6 is the confirmed final-stage runtime for the AMD Developer Hackathon ACT II Track 1: Hybrid Token-Efficient Routing Agent.

Event: https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii

Team: `team-2168`, 1 member, `dr.wbsite@gmail.com`

Timeline: starts `2026-07-06 16:00 British Summer Time`, ends `2026-07-12 16:00 British Summer Time`

## Mission

Complete the official Track 1 task batch accurately while minimizing judged Fireworks tokens. Accuracy is the first gate. Local inference inside the submitted container is allowed and counts as zero judged Fireworks tokens.

Version 6 uses:

- CPU-only Ollama bundled in the runtime image;
- local model `nemotron-3-nano:4b`;
- official batch input `/input/tasks.json`;
- official batch output `/output/results.json`;
- Fireworks fallback in production through `FIREWORKS_BASE_URL`, `FIREWORKS_API_KEY`, and `ALLOWED_MODELS`;
- a separate analytics-only UI image that is not for submission.

## Official Runtime Contract

On startup, the submission container reads:

```text
/input/tasks.json
```

The input must be a top-level JSON array. Each record must contain only:

```json
{"task_id": "task-1", "prompt": "Complete task prompt"}
```

Before successful exit, the runtime writes:

```text
/output/results.json
```

The output is a top-level JSON array. Each record contains only:

```json
{"task_id": "task-1", "answer": "..."}
```

The runtime preserves task IDs, preserves input order, exits `0` on success, exits non-zero on failure, and does not require a UI action, interactive input, manual API request, or server lifecycle to begin work. Internal audit records are written outside `/output/results.json`, under `/output/audit` by default.

## Containers

Submission runtime targets are defined in [Dockerfile.version6](/home/user/repos/Hatikva/AMD_HACKERTHON_APP/Dockerfile.version6):

```text
version6-staging
version6-production
```

They use the same code path, bundled model, runtime entrypoint, input/output behavior, validation, audit behavior, and no-UI posture.

The only intended difference:

- `version6-staging` uses Ollama Cloud through the native `/api/chat` API for non-submission remote fallback testing.
- `version6-production` uses Fireworks fallback through `FIREWORKS_BASE_URL`.

Production must not route inference to any external hosted provider other than Fireworks. Staging is explicitly `NOT_FOR_SUBMISSION`.

Build staging:

```bash
scripts/stage-version5-ollama-runtime.sh
docker build -f Dockerfile.version6 --target version6-staging -t amd-hackathon:version6-staging .
```

Run staging with official mounts:

```bash
docker run --rm \
  -e OLLAMA_API_KEY="$OLLAMA_API_KEY" \
  -e OLLAMA_CLOUD_BASE_URL="https://ollama.com" \
  -e STAGING_REMOTE_PROVIDER="ollama-cloud" \
  -e STAGING_ALLOWED_MODELS="minimax-m3:cloud,nemotron-3-super:cloud,gpt-oss:20b-cloud,gemma4:31b-cloud" \
  -e STAGING_INFERENCE_MODEL="minimax-m3:cloud" \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  amd-hackathon:version6-staging
```

`STAGING_ALLOWED_MODELS` is a development candidate list for Ollama Cloud. It is separate from production `ALLOWED_MODELS`, which is the harness-provided Fireworks allow list for official judging. Ollama Cloud token metadata is staging comparison data only and is reported as `official_fireworks_token_score=NOT_MEASURED`.

See [Version 6 Ollama Cloud Staging](docs/VERSION6_STAGING_OLLAMA_CLOUD.md) for the native API contract and verified supplied-ID mappings.

Build production:

```bash
scripts/stage-version5-ollama-runtime.sh
docker build -f Dockerfile.version6 --target version6-production -t amd-hackathon:version6-production .
```

Run production locally with official mounts:

```bash
docker run --rm \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e FIREWORKS_BASE_URL="$FIREWORKS_BASE_URL" \
  -e ALLOWED_MODELS="$ALLOWED_MODELS" \
  -v "$PWD/input:/input:ro" \
  -v "$PWD/output:/output" \
  amd-hackathon:version6-production
```

The official evaluator provides `/input/tasks.json` and reads `/output/results.json`.

## Analytics UI

The analytics UI is a separate read-only container target:

```text
version6-analytics-ui
```

It is analytics only, not for submission, and not required by the official runtime. It has no task input form and no live task execution endpoint.

Generate analytics:

```bash
python3 -m amd_hackathon_app.cli build-version6-analytics
```

The active analytics UI reads only `qualification/results/*.json`. Older Version 4/5 seed results used for UI smoke testing are archived outside the active display path under `qualification/archive/`; keep new Version 6 staging calibration results in `qualification/results/` only while they should be visible in the UI.

Build and run the UI:

```bash
docker build -f Dockerfile.version6-ui -t amd-hackathon:version6-analytics-ui .
docker run --rm --network host amd-hackathon:version6-analytics-ui
```

Open `http://127.0.0.1:18084`.

## Validation

Run local tests:

```bash
python3 -m unittest
```

Generate the Version 6 analytics artifact:

```bash
python3 -m amd_hackathon_app.cli build-version6-analytics
```

Inspect and smoke the Version 6 images:

```bash
scripts/verify-version6-images.sh amd-hackathon:version6-staging amd-hackathon:version6-production
```

The image inspection checks compressed image size, confirms Ollama and the Nemotron blob are present, and fails if submission images contain UI assets, benchmark folders, qualification artifacts, `.env`, or obvious evaluator/answer fixtures.

## Current Blockers

- Full hidden-task accuracy is unknowable until official scoring.
- Current evidence has not promoted any local jurisdiction to certified authority.
- Production fallback requires `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL`, and `ALLOWED_MODELS`.
- Final public image publication requires registry credentials and a final image inspection pass.
