# Benchmark Status

## Version 5 Canonical Category Benchmark

Canonical suite: `benchmarks/categories/version5_local_category_benchmarks_v2.json`

Suite identifier: `version5-category-benchmark-v2`

SHA-256: `24e9981521b91173e70f17910f14740ca6c159c7165e7272196835fcc2b9d6e7`

Status: canonical offline qualification suite.

The Version 2 suite replaces any prior Version 1 category benchmark for active Version 5 qualification. It contains eight canonical task categories, five progressively difficult tasks per category, and 40 tasks total.

The suite is not live input. It must not be copied to `/input/tasks.json`, and live task processing must not execute the benchmark or mutate model authorization. Benchmark runs produce reviewable qualification artifacts under `qualification/results/`.

Current evaluator status:

- implemented: normalized exact match, numeric exact match, label exact match, unordered set match, ordered list match, JSON deep exact match, summary rubric;
- blocked pending isolated sandbox: Python unit-test and behavioral-test evaluators.

Mock benchmark runs validate wiring only and are not model qualification evidence.

## Version 5 Selected Local Model

Selected model: `nemotron-3-nano:4b`

Selected GGUF path in image: `/app/models/nemotron-3-nano-4b.gguf`

Observed local source paths:

- `.local/ollama-backup-gguf-import/backup-nemotron-3-nano-4b.gguf`
- `/mnt/g/ollama-models-backup-container/models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970`

Observed size: `2,837,586,496` bytes.

Observed SHA-256: `527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970`.

The Version 5 local runtime is `OLLAMA_CERTIFIED` for the CPU-only Ollama path, but no jurisdiction is currently `LOCAL_CERTIFIED`. Real Version 5 benchmark passes through provider `version5-ollama` must run before local-first routing is enabled.

## Version 5 Runtime Experiments

### llama.cpp bundled image

Final verified image:

```text
image: amd-hackathon-version5:nemotron
llama.cpp commit: 07d937828636e305bc0cfe738b288f9ab05ff748
uncompressed image size: 3,019,067,622 bytes
compressed image size: 2,860,434,793 bytes
preflight under --memory=4g --cpus=2: passed
```

Runtime evidence:

- older `b5753` llama.cpp did not recognize `nemotron_h`;
- current pinned llama.cpp loads the architecture but direct local inference under `--memory=4g --cpus=2` was not viable;
- default context/generation timed out;
- minimal one-token/context-128 smoke was OOM-killed with exit `137`.

### Ollama CPU-only final runtime path

Host Ollama evidence:

```text
ollama client/server version: 0.31.1
model: nemotron-3-nano:4b
HTTP smoke, num_ctx=128, num_predict=8, num_thread=2: response 4 in 27.63s
loaded runner RSS with OLLAMA_CONTEXT_LENGTH=128: about 998 MB
```

Containerized CPU-only experiment:

```text
image: amd-hackathon-version5:ollama
uncompressed image size: 3,038,198,978 bytes
compressed image size after final provider promotion: 2,866,482,218 bytes
smoke under --memory=4g --cpus=2: passed
smoke answer: 4
smoke elapsed: 19.98s
oom_killed: false
```

The CPU-only Ollama image is about `6,030,430` bytes larger compressed than the llama.cpp image, but it completed the constrained smoke where direct llama.cpp did not. It is the final Version 5 local runtime path under provider `version5-ollama`; this does not promote any jurisdiction to `LOCAL_CERTIFIED`.

Host Ollama full category pass:

```text
result: qualification/results/version5-ollama-host-real.json
provider: ollama-demo
model: nemotron-3-nano:4b
overall_tasks: 40
overall_passed: 16
overall_accuracy: 0.40
runtime_failures: 0
validation_failures: 0
judged_fireworks_tokens: 0
elapsed_seconds: 362.17
```

That host benchmark is retained as qualification evidence from the old demo path. Final-candidate evidence must be rerun through provider `version5-ollama`, with model-visible tasks projected to only `task_id` and `prompt` and evaluator metadata withheld.

Promotion into authorization records requires:

- overall accuracy at or above the selected candidate gate;
- per-category pass rate above the category threshold;
- zero unsupported evaluator types except sandbox-blocked code evaluators;
- validator coverage adequate for the jurisdiction;
- local fallback plus repair tokens lower than Version 4 judged Fireworks tokens;
- memory below about 4 GB RAM and latency acceptable under 2 vCPU.

Latest local benchmark:

```text
benchmarks/results/profile-benchmark-20260625T191604Z.jsonl
provider_override: local
local_model: Phi-4-mini-instruct-GGUF
```

## Findings

| Scenario | Result | Evidence |
| --- | --- | --- |
| `classification-basic` | pass | Local Phi returned `docs`; validation passed; 99 total tokens; 1448 ms. |
| `json-extraction-basic` | fail strict JSON | Local Phi returned fenced markdown JSON; validation failed with `invalid_json`; 120 total tokens; 4113 ms. |
| `reasoning-escalation-boundary` | local forced pass, router should escalate | Local Phi produced a sensible answer, but the router reason remains `difficulty_above_local_threshold`; normal routing should use Fireworks once verified. |

## Profile Consequence

`balanced-local-first` now sets `json_extraction.max_local_difficulty` to `0`. Strict JSON tasks should route away from local Phi until the app adds either stricter prompting, output repair, or evidence that a local profile passes strict JSON validation.

## Next Pipeline Actions

- Verify Fireworks provider with environment-provided credentials.
- Run routed benchmarks without `PROVIDER_OVERRIDE=local` after Fireworks is available.
- Add local output-repair experiments only if they improve strict JSON accuracy without excessive retry tokens.
