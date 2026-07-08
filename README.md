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

## Environment

Required for Fireworks execution:

```bash
export FIREWORKS_API_KEY=...
export FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
export ALLOWED_MODELS=model-a,model-b
```

Optional demo-local Ollama settings:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
export MODEL_NAME=qwen2.5-coder:3b
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_CONTEXT_LENGTH=2048
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
- `docs/repo-structure.json`

These files describe operation and compliance without exposing private benchmark thresholds, private planning critique, or internal planning terminology.

## Known Limitations

- The benchmark-derived model eligibility matrix is represented by the current deterministic selector and must be populated with measured evidence before Version 4 final scoring.
- Fireworks execution requires credentials and an `ALLOWED_MODELS` value from the runtime environment.
- Ollama execution is demo-only and is excluded from the final scoring path.
