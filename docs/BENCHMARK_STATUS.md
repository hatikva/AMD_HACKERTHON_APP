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

- Verify Fireworks provider with environment-provided credentials.
- Run routed benchmarks without `PROVIDER_OVERRIDE=local` after Fireworks is available.
- Add local output-repair experiments only if they improve strict JSON accuracy without excessive retry tokens.
