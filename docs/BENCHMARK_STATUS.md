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
