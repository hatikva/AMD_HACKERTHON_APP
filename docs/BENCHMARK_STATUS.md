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

Categorization risk is tracked in `docs/CATEGORIZATION_RISK.md`. The categorizer must be evaluated with official-shape tasks containing only `task_id` and `prompt`; expected categories and evaluator metadata remain evaluator-only data joined by `task_id`.

Current reviewed-evidence analytics are generated at `docs/version5_authority_analytics.json`. That artifact does not mutate runtime authorization and does not promote local jurisdictions.

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
compressed image size after final provider promotion: 2,866,482,542 bytes
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

## Current Candidate Benchmark Evidence

All rows below use canonical suite `version5-category-benchmark-v2` with SHA-256 `24e9981521b91173e70f17910f14740ca6c159c7165e7272196835fcc2b9d6e7`.

| Candidate | Result file | Provider path | Model | Passed | Accuracy | Judged Fireworks tokens | Authorization effect |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Version 4 Fireworks-only | `qualification/results/version4-fireworks-real.json` | `fireworks` | `accounts/fireworks/models/minimax-m3` | 21/40 | 0.525 | 37,998 | none; `PENDING_POLICY_REVIEW` |
| Version 5 policy fallback | `qualification/results/version5-fallback-real.json` | `version5` policy, all tasks routed to Fireworks because no local jurisdiction is certified | Fireworks `accounts/fireworks/models/minimax-m3`; candidate metadata records local model `nemotron-3-nano:4b` | 22/40 | 0.55 | 91,612 | none; `PENDING_POLICY_REVIEW` |
| Version 5 local model qualification baseline | `qualification/results/version5-ollama-host-real.json` | `ollama-demo` host path, not final provider identity | `nemotron-3-nano:4b` | 16/40 | 0.40 | 0 | none; not final-candidate evidence |

The latest final-runtime local model test is the constrained container smoke, not a 40-task final-candidate benchmark:

```text
provider_identity: version5-ollama
image: amd-hackathon-version5:ollama
compressed_image_bytes: 2,866,482,542
constraint: --memory=4g --cpus=2
result: oom_killed=false, exit_code=0
output: [{"answer":"4","task_id":"smoke_math"}]
```

`version5-ollama` must still run the full 40-task suite before any jurisdiction can be promoted to `LOCAL_CERTIFIED`.

## Work Scope Evidence Matrix

Scope pass means all 5 benchmark tasks for that category passed. Partial means at least one, but not all, category tasks passed. This table is evidence, not automatic runtime authorization.

| Work scope / category | Version 4 Fireworks `minimax-m3` | Version 5 fallback using Fireworks `minimax-m3` | Local `nemotron-3-nano:4b` host baseline |
| --- | --- | --- | --- |
| Factual knowledge | partial, 4/5, 1,561 Fireworks tokens | pass, 5/5, 1,600 Fireworks tokens | partial, 4/5, 0 Fireworks tokens |
| Mathematical reasoning | pass, 5/5, 1,491 Fireworks tokens | pass, 5/5, 1,439 Fireworks tokens | pass, 5/5, 0 Fireworks tokens |
| Sentiment classification | pass, 5/5, 1,296 Fireworks tokens; validation failures require review | pass, 5/5, 1,284 Fireworks tokens; validation failures require review | fail, 0/5, 0 Fireworks tokens |
| Text summarisation | fail, 0/5, 17,391 Fireworks tokens | fail, 0/5, 67,708 Fireworks tokens | fail, 0/5, 0 Fireworks tokens |
| Named entity recognition | partial, 2/5, 2,016 Fireworks tokens | partial, 2/5, 2,075 Fireworks tokens | partial, 2/5, 0 Fireworks tokens |
| Code debugging | fail, 0/5, 5,049 Fireworks tokens | fail, 0/5, 4,126 Fireworks tokens | fail, 0/5, 0 Fireworks tokens |
| Logical/deductive reasoning | pass, 5/5, 2,275 Fireworks tokens | pass, 5/5, 2,406 Fireworks tokens | pass, 5/5, 0 Fireworks tokens |
| Code generation | fail, 0/5, 6,919 Fireworks tokens | fail, 0/5, 10,974 Fireworks tokens | fail, 0/5, 0 Fireworks tokens |

Current authorization interpretation:

- `accounts/fireworks/models/minimax-m3` has positive evidence for mathematical reasoning, logical/deductive reasoning, and sentiment classification. Factual knowledge is stronger in the Version 5 fallback run but still requires policy review because the two Fireworks runs differ.
- `nemotron-3-nano:4b` has local qualification evidence for mathematical reasoning and logical/deductive reasoning only. It is not `LOCAL_CERTIFIED` because the evidence came through `ollama-demo`, not final `version5-ollama`, and thresholds are not approved.
- No model/work-scope pair is currently promoted into a runtime authorization registry by these benchmark runs.

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
