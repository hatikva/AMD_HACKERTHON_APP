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

Version 5 is represented as a llama.cpp local-first submission candidate. It preserves Version 3 and adds a conservative candidate mode:

- local inference runtime: `llama.cpp`;
- default binary path: `/app/bin/llama-cli`;
- default model path: `/app/models/model.gguf`;
- default context length: `2048`;
- default thread count: `2`;
- Fireworks fallback: `FIREWORKS_BASE_URL` with model IDs from `ALLOWED_MODELS`;
- local certification status: blocked until an exact GGUF artifact and benchmark evidence exist.

No Work Jurisdiction is marked `LOCAL_CERTIFIED` yet. Until a selected GGUF model, license, size, memory profile, and benchmark results are recorded, Version 5 routes through the Fireworks fallback path.

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

Optional Version 5 llama.cpp settings:

```bash
export LLAMA_CPP_BINARY=/app/bin/llama-cli
export LLAMA_MODEL_PATH=/app/models/model.gguf
export LLAMA_MODEL_NAME=selected-gguf-model
export LLAMA_CONTEXT_LENGTH=2048
export LLAMA_THREADS=2
export LLAMA_MAX_TOKENS=128
export LLAMA_TIMEOUT_SECONDS=60
export LOCAL_GENERATION_CONCURRENCY=1
```

## Input And Output

Final-compatible batch execution reads `/input/tasks.json` and writes `/output/results.json`.

Example input:

```json
{
  "tasks": [
    {
      "id": "task-1",
      "prompt": "Summarize the supplied paragraph in one sentence.",
      "task_family": "summarization",
      "expected_format": "text"
    }
  ]
}
```

Run with Fireworks:

```bash
python3 -m amd_hackathon_app.cli run-tasks \
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

Open `http://127.0.0.1:18083`. The UI accepts `/input/tasks.json`-style task payloads, shows outputs, token counts, validation state, latency, selected provider/model, and lightweight analytics for Version 3, Version 4, and Version 5 comparison. Version 3 uses the Ollama demo path. Version 4 requires Fireworks environment variables. Version 5 remains blocked until the selected GGUF artifact and certification evidence exist.

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
python3 -m amd_hackathon_app.cli run-tasks \
  --input /input/tasks.json \
  --output /output/results.json \
  --provider version5
```

This currently requires Fireworks configuration because the local GGUF artifact is not finalized and local jurisdictions are not certified.

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

## Public Docs

Public JSON docs live under `docs/`:

- `docs/concept.json`
- `docs/algorithm.json`
- `docs/allowed-models.json`
- `docs/FIREWORKS_MODEL_RESOURCES.md`
- `docs/repo-structure.json`

These files describe operation and compliance without exposing private benchmark thresholds, private planning critique, or internal planning terminology.

## Known Limitations

- The benchmark-derived model eligibility matrix is represented by the current deterministic selector and must be populated with measured evidence before Version 4 final scoring.
- Fireworks execution requires credentials and an `ALLOWED_MODELS` value from the runtime environment.
- Ollama execution is demo-only and is excluded from the final scoring path.
- Version 5 local-first execution is blocked until the exact GGUF model artifact, license, expected memory use, image path, and jurisdiction certification matrix are finalized.
