# Container Packaging

Development and submission packaging are separate concerns.

## Development

`compose.dev.yml` uses named volumes so candidate models and Lemonade backend state are not repeatedly downloaded:

- `lemonade-cache`
- `lemonade-llama`
- `lemonade-recipe`

These volumes are not part of the image. A container that depends on them is not self-contained.

## Submission

The final submission must not depend on host bind mounts or pre-existing model volumes. Do not commit model weights to Git.

Only one selected local model should be embedded in the Version 5 image. The selected artifact is `nemotron-3-nano:4b`, staged as `models/version5/nemotron-3-nano-4b.gguf` and copied to `/app/models/nemotron-3-nano-4b.gguf`. Runtime downloads are not part of the final Version 5 path.

## Offline Test Requirement

Before claiming a submission image is self-contained:

1. Build the image from a clean context.
2. Run it without model volumes or bind mounts.
3. Disable outbound network access.
4. Confirm the selected model loads and serves a non-empty response.

Compose YAML alone does not prove scoring accepts multiple containers or that weights are self-contained.

Use:

```bash
scripts/stage-version5-model.sh
scripts/verify-version5-image.sh amd-hackathon-version5:local
```

The verification script builds `Dockerfile.version5`, checks the gzip-compressed saved image is below 10 GB, and runs `amd-router preflight` with `--memory=4g --cpus=2`.

## Ollama Runtime Experiment

An experimental CPU-only Ollama image can be built from the host Ollama installation and existing local model cache without pulling `ollama/ollama:latest`:

```bash
scripts/stage-version5-ollama-runtime.sh
docker build -f Dockerfile.version5-ollama -t amd-hackathon-version5:ollama .
```

The staging script copies only:

- `/usr/local/bin/ollama`;
- CPU shared libraries from `/usr/local/lib/ollama`;
- the selected `nemotron-3-nano:4b` Ollama manifest and required blobs.

It intentionally excludes the CUDA and Vulkan backend directories from the host Ollama install. The staged payload remains under ignored `models/version5-ollama/` and must not be committed.

Observed on 2026-07-10:

```text
llama.cpp compressed image: 2,860,434,793 bytes
CPU-only Ollama compressed image: 2,866,465,223 bytes
delta: +6,030,430 bytes for Ollama
Ollama constrained smoke: passed under --memory=4g --cpus=2
llama.cpp constrained direct inference: OOM-killed under --memory=4g --cpus=2
```

The Ollama image is still experimental. It uses the `ollama-demo` provider path and is not final-mode compliant until routing, certification, startup behavior, and benchmark promotion policy are deliberately updated.

## Version 5 Qualification Benchmark Packaging

`benchmarks/categories/version5_local_category_benchmarks_v2.json` is an offline qualification suite, not a live task fixture.

Do not place the benchmark in `/input/tasks.json`, `/output`, or automatic live-processing paths. If a development or qualification image includes the benchmark, treat it as evaluator-only material: it contains expected answers, rubrics, and reference solutions that must never be sent to a tested model.

Production submission packaging should include qualification artifacts only when explicitly required by the submission process. Otherwise, use benchmark-derived, reviewed authorization records rather than bundling evaluator answers into the runtime image.
