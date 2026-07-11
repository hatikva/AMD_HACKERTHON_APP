# AMD Hackathon App

Most Innovative Routing System for AMD Developer Hackathon Track 1.

This repository is the application/runtime repository for `hatikva/AMD_HACKERTHON_APP`. The planning source of truth is `hatikva/AMD_HACKERTHON_IMPLEMENTATION_PLAN`.

## Current Mode

The active implementation is a Version 3 demo architecture:

- deterministic local control plane;
- Work Jurisdiction routing;
- task-family aware prompt shaping;
- context selection and evidence packing;
- answer schema selection;
- deterministic validation;
- structural repair where safe;
- Fireworks provider path through `FIREWORKS_BASE_URL`;
- optional Ollama demo path for `qwen2.5-coder:3b`.

Version 3 is not the final Fireworks-only scoring architecture. Version 4 final mode must use Fireworks-only inference, must source model IDs from `ALLOWED_MODELS`, must not hardcode final model IDs, and must not bundle model weights.

The local demo model is demo/development-only. Local demo inference uses Ollama, not Lemonade. The legacy `pod_amd_hackerthon_app` Podman pod and old Lemonade files are preserved as historical evidence and are not the active Version 3 runtime.

## Version 5 Candidate

Version 5 is represented as an Ollama local-runtime submission candidate. It preserves Version 3 and adds a conservative candidate mode:

- local inference runtime: CPU-only Ollama;
- final local provider identity: `version5-ollama`;
- selected local model: `nemotron-3-nano:4b`;
- bundled model store: `/app/ollama-models`;
- selected GGUF SHA-256: `527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970`;
- selected GGUF size: `2,837,586,496` bytes;
- default context length: `128`;
- loaded models / parallel generations: `1`;
- Fireworks fallback: `FIREWORKS_BASE_URL` with model IDs from `ALLOWED_MODELS`;
- runtime certification status: `OLLAMA_CERTIFIED`;
- jurisdiction certification status: no Work Jurisdiction is `LOCAL_CERTIFIED` until real benchmark evidence is reviewed and promoted.

No Work Jurisdiction is marked `LOCAL_CERTIFIED` yet. Until memory, latency, accuracy, validator coverage, and promotion thresholds are recorded, Version 5 routes through the Fireworks fallback path.

Direct llama.cpp packaging is retained as evidence after `nemotron-3-nano:4b` failed direct llama.cpp inference under the 4 GB / 2 vCPU envelope. The CPU-only Ollama image completed a constrained one-task smoke and is only about 6 MB larger compressed than the llama.cpp image, so `version5-ollama` is the promoted Version 5 local runtime path.

## Version 5 Qualification Benchmark

The canonical offline Version 5 primary-category benchmark is:

```text
benchmarks/categories/version5_local_category_benchmarks_v2.json
```

Suite identifier:

```text
version5-category-benchmark-v2
```

Content hash:

```text
sha256:24e9981521b91173e70f17910f14740ca6c159c7165e7272196835fcc2b9d6e7
```

This repository-owned Version 2 suite contains eight canonical task categories, five progressively difficult tasks per category, and 40 tasks total. It is used only for offline model qualification before live task execution. It is never executed as part of live `/input/tasks.json` processing, and it does not dynamically authorize models during runtime routing.

Validate the benchmark:

```bash
python3 -m amd_hackathon_app.cli validate-category-benchmark
```

Run a dry wiring benchmark with the mock provider:

```bash
python3 -m amd_hackathon_app.cli benchmark-categories \
  --provider mock \
  --output qualification/results/mock-version5-category-benchmark.json
```

Run a candidate qualification pass by recording the exact provider and model:

```bash
python3 -m amd_hackathon_app.cli benchmark-categories \
  --suite benchmarks/categories/version5_local_category_benchmarks_v2.json \
  --provider fireworks \
  --model "$ONE_ALLOWED_MODEL" \
  --output qualification/results/fireworks-candidate.json
```

Mock benchmark output validates wiring only. It is not model qualification evidence.

## Environment

Required for Fireworks execution:

```bash
export FIREWORKS_API_KEY=...
export FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
export ALLOWED_MODELS=model-a,model-b
```

Observed Fireworks resource names for the current Track 1 planning seed list are documented in `docs/FIREWORKS_MODEL_RESOURCES.md` and `docs/allowed-models.json`. The app does not hardcode that list for final scoring.

Optional demo-local Ollama settings:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
export MODEL_NAME=qwen2.5-coder:3b
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_CONTEXT_LENGTH=2048
```

Optional Version 5 final Ollama runtime settings:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
export OLLAMA_MODEL_NAME=nemotron-3-nano:4b
export OLLAMA_CONTEXT_LENGTH=128
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_TIMEOUT_SECONDS=300
```

Retained Version 5 llama.cpp evidence settings:

```bash
export LLAMA_CPP_BINARY=/app/bin/llama-cli
export LLAMA_MODEL_PATH=/app/models/nemotron-3-nano-4b.gguf
export LLAMA_MODEL_NAME=nemotron-3-nano:4b
export LLAMA_CONTEXT_LENGTH=2048
export LLAMA_THREADS=2
export LLAMA_MAX_TOKENS=128
export LLAMA_TIMEOUT_SECONDS=60
export LOCAL_GENERATION_CONCURRENCY=1
```

## Input And Output

Final-compatible batch execution reads `/input/tasks.json` and writes `/output/results.json`.

The Version 5 production runtime accepts the official minimal task array containing only `task_id` and `prompt`, classifies each task internally, and writes the official minimal results array containing only `task_id` and `answer`.

Example input:

```json
[
  {
    "task_id": "task-1",
    "prompt": "Summarize the supplied paragraph in one sentence."
  }
]
```

Example output:

```json
[
  {
    "task_id": "task-1",
    "answer": "..."
  }
]
```

Run with Fireworks:

```bash
python3 -m amd_hackathon_app.cli run-submission \
  --input /input/tasks.json \
  --output /output/results.json
```

Run the offline mock verification path:

```bash
python3 -m amd_hackathon_app.cli run-scenario --scenario classification-basic --provider mock
```

Run the optional Ollama demo path:

```bash
python3 -m amd_hackathon_app.cli run-scenario --scenario classification-basic --provider ollama-demo
```

Run the Version 3 UI:

```bash
python3 -m amd_hackathon_app.cli ui --host 127.0.0.1 --port 18083
```

Open `http://127.0.0.1:18083`. The UI accepts `/input/tasks.json`-style task payloads, shows outputs, token counts, validation state, latency, selected provider/model, and lightweight analytics for Version 3, Version 4, and Version 5 comparison. Version 3 uses the Ollama demo path. Version 4 requires Fireworks environment variables. Version 5 uses an Ollama-certified runtime path only after jurisdiction-specific authorization evidence exists.

The same UI includes `Version 5 Results And Analytics` and `Internal Tooling Analysis` views. These views read local qualification result JSONs and reviewed-evidence analytics; they do not call Fireworks, start Ollama, mutate runtime authorization, or certify local jurisdictions.

Run the same UI as a separate container:

```bash
podman build -f Dockerfile.ui -t amd-hackathon-ui:version3 .
podman run --rm --network host \
  -e UI_HOST=127.0.0.1 \
  -e UI_PORT=18083 \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434/v1 \
  -e MODEL_NAME=qwen2.5-coder:3b \
  amd-hackathon-ui:version3
```

Run the Version 5 candidate path:

```bash
python3 -m amd_hackathon_app.cli run-submission \
  --input /input/tasks.json \
  --output /output/results.json \
  --provider version5
```

This currently requires Fireworks configuration because no local jurisdictions are certified, even though the Version 5 Ollama runtime path is certified.

Run the Version 5 Ollama final-candidate benchmark path directly:

```bash
python3 -m amd_hackathon_app.cli run-submission \
  --input /input/tasks.json \
  --output /output/results.json \
  --provider version5-ollama
```

Stage the selected GGUF for a Version 5 container build:

```bash
scripts/stage-version5-model.sh
```

Build and verify the Version 5 image with the selected GGUF bundled:

```bash
scripts/verify-version5-image.sh amd-hackathon-version5:local
```

That check builds `Dockerfile.version5`, verifies the compressed image stays below 10 GB, and runs `amd-router preflight` under a 4 GB RAM / 2 vCPU container limit.

Build and verify the CPU-only Ollama final runtime image:

```bash
scripts/stage-version5-ollama-runtime.sh
scripts/verify-version5-ollama-image.sh amd-hackathon-version5:ollama
```

Observed comparison on 2026-07-10:

- llama.cpp image: `2,860,434,793` compressed bytes;
- CPU-only Ollama image: `2,866,482,542` compressed bytes after final provider promotion;
- Ollama constrained smoke: passed under `--memory=4g --cpus=2`, answer `4`, elapsed `19.98s`;
- llama.cpp constrained direct inference: OOM-killed for `nemotron-3-nano:4b`.

The repository-owned Version 5 benchmark format is intentionally richer. During offline qualification it is split into a model-visible official-format task file and evaluator-only grading data. The normal runtime receives only the official-format task file.

Grading is optional and development-only. When no benchmark file is supplied, the application performs inference and writes results without attempting to grade them.

The final submission image excludes benchmark tasks, expected answers, evaluator metadata, and grading fixtures.

## Development

Create a local environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

Run the app audit gate:

```bash
scripts/validate-app.sh
```

Inspect environment:

```bash
python3 -m amd_hackathon_app.cli preflight
```

Build the Version 5 reviewed-evidence analytics artifact:

```bash
PYTHONPATH=src python3 -m amd_hackathon_app.cli build-version5-analytics \
  --results-dir qualification/results \
  --output docs/version5_authority_analytics.json
```

## Public Docs

Public JSON docs live under `docs/`:

- `docs/concept.json`
- `docs/algorithm.json`
- `docs/allowed-models.json`
- `docs/FIREWORKS_MODEL_RESOURCES.md`
- `docs/BENCHMARK_STATUS.md`
- `docs/CATEGORIZATION_RISK.md`
- `docs/version5_authority_analytics.json`
- `docs/repo-structure.json`

These files describe operation and compliance without exposing private benchmark thresholds, private planning critique, or internal planning terminology.

## Known Limitations

- The benchmark-derived model eligibility matrix is represented by the current deterministic selector and must be populated with measured evidence before Version 4 final scoring.
- Fireworks execution requires credentials and an `ALLOWED_MODELS` value from the runtime environment.
- Version 3 Ollama execution remains demo-only under `ollama-demo`; Version 5 uses the separate `version5-ollama` provider identity.
- Version 5 local-first execution is blocked until the selected `nemotron-3-nano:4b` artifact has real accuracy, latency, fallback, and jurisdiction-promotion evidence through `version5-ollama`.
