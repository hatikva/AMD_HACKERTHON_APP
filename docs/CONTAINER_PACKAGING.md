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

Only one selected local model should be embedded in the Version 5 image. The final Version 5 runtime path is CPU-only Ollama with `nemotron-3-nano:4b`, staged under `models/version5-ollama/` with its manifest and required blobs. Runtime downloads are not part of the final Version 5 path.

## Offline Test Requirement

Before claiming a submission image is self-contained:

1. Build the image from a clean context.
2. Run it without model volumes or bind mounts.
3. Disable outbound network access.
4. Confirm the selected model loads and serves a non-empty response.

Compose YAML alone does not prove scoring accepts multiple containers or that weights are self-contained.

The older direct llama.cpp image is retained as runtime evidence only:

```bash
scripts/stage-version5-model.sh
scripts/verify-version5-image.sh amd-hackathon-version5:local
```

That verification builds `Dockerfile.version5`, checks the gzip-compressed saved image is below 10 GB, and runs `amd-router preflight` with `--memory=4g --cpus=2`. Direct llama.cpp inference with the selected Nemotron artifact was OOM-killed under the target envelope, so it is not the final Version 5 local runtime path.

Use this for the promoted Version 5 Ollama runtime path:

```bash
scripts/stage-version5-ollama-runtime.sh
scripts/verify-version5-ollama-image.sh amd-hackathon-version5:ollama
```

The staging script copies only:

- `/usr/local/bin/ollama`;
- CPU shared libraries from `/usr/local/lib/ollama`;
- the selected `nemotron-3-nano:4b` Ollama manifest and required blobs.

It intentionally excludes the CUDA and Vulkan backend directories from the host Ollama install. The staged payload remains under ignored `models/version5-ollama/` and must not be committed.

Observed on 2026-07-10:

```text
llama.cpp compressed image: 2,860,434,793 bytes
CPU-only Ollama compressed image after final provider promotion: 2,866,482,218 bytes
delta: +6,030,430 bytes for Ollama
Ollama constrained smoke: passed under --memory=4g --cpus=2
llama.cpp constrained direct inference: OOM-killed under --memory=4g --cpus=2
```

The Ollama image now uses the final provider identity `version5-ollama`. This certifies the local runtime path only. Jurisdiction-level local routing remains blocked until benchmark results through `version5-ollama` meet reviewed thresholds and are promoted into authorization records.

## Version 5 Qualification Benchmark Packaging

`benchmarks/categories/version5_local_category_benchmarks_v2.json` is an offline qualification suite, not a live task fixture.

Do not place the benchmark in `/input/tasks.json`, `/output`, or automatic live-processing paths. If a development or qualification image includes the benchmark, treat it as evaluator-only material: it contains expected answers, rubrics, and reference solutions that must never be sent to a tested model.

Production submission packaging should include qualification artifacts only when explicitly required by the submission process. Otherwise, use benchmark-derived, reviewed authorization records rather than bundling evaluator answers into the runtime image.
