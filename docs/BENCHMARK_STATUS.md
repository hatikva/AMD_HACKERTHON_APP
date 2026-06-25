# Benchmark Status

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

- Verify Fireworks provider success with environment-provided credentials.
- Run routed profile-pair benchmarks across `phi-nemotron-balanced`, `phi-qwen-coder-balanced`, and `phi-fireworks-balanced`.
- Add local output-repair experiments only if they improve strict JSON accuracy without excessive retry tokens.

## Fireworks Verification

Fireworks is integrated as a remote provider, but real inference is not yet verified. On 2026-06-25, the configured Fireworks profile route reached the API and returned HTTP 404 indicating the model was not found, inaccessible, or not deployed for the account. A model-list request returned HTTP 401 for the provided credential value. The app now surfaces those provider errors clearly without logging API keys.

## Profile-Pair Update

The benchmark/UI path now treats a profile as a local/remote model pair plus routing policy. Seed pairs are:

| Profile | Local | Remote |
| --- | --- | --- |
| `phi-nemotron-balanced` | `Phi-4-mini-instruct-GGUF` | `ollama_cloud` / `nemotron-3-ultra:cloud` |
| `phi-qwen-coder-balanced` | `Phi-4-mini-instruct-GGUF` | `ollama_cloud` / `qwen3-coder:480b-cloud` |
| `phi-fireworks-balanced` | `Phi-4-mini-instruct-GGUF` | `fireworks` / `accounts/fireworks/models/llama-v3p3-70b-instruct` |
