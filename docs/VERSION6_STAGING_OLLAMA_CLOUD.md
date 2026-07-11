# Version 6 Ollama Cloud Staging

Status: `STAGING_PROVIDER_IMPLEMENTED`

Version 6 staging is a production-shaped development environment. It is `NOT_FOR_SUBMISSION`.

Production remains Fireworks-only for remote fallback:

```text
production_remote_provider = FIREWORKS_ONLY
ollama_cloud_available_in_production = false
```

## Runtime Contract

Staging keeps the official batch contract:

- read `/input/tasks.json`;
- require a top-level array of records containing only `task_id` and `prompt`;
- write `/output/results.json`;
- emit only `task_id` and `answer` in official results;
- write telemetry separately under `/output/audit`.

## Environment

Ollama Cloud staging requires:

```text
VERSION6_REMOTE_FALLBACK=staging
STAGING_REMOTE_PROVIDER=ollama-cloud
OLLAMA_API_KEY=<runtime secret>
OLLAMA_CLOUD_BASE_URL=https://ollama.com
STAGING_ALLOWED_MODELS=minimax-m3:cloud,nemotron-3-super:cloud,gpt-oss:20b-cloud,gemma4:31b-cloud
STAGING_INFERENCE_MODEL=<one supplied staging model id>
```

The adapter uses:

```text
POST https://ollama.com/api/chat
Authorization: Bearer <OLLAMA_API_KEY>
stream=false
```

It does not call `/chat/completions`.

## Model Verification

`/api/tags` returned HTTP `200` on 2026-07-11. The supplied candidate IDs map to these API-visible IDs:

| Supplied ID | API model ID | Status |
| --- | --- | --- |
| `minimax-m3:cloud` | `minimax-m3` | `STAGING_MODEL_VERIFIED`; direct smoke returned `4` |
| `nemotron-3-super:cloud` | `nemotron-3-super` | listed by `/api/tags`; initial direct smoke timed out; later one-task staging container smoke returned `4` |
| `gpt-oss:20b-cloud` | `gpt-oss:20b` | `STAGING_MODEL_VERIFIED`; direct smoke returned `4` |
| `gemma4:31b-cloud` | `gemma4:31b` | `STAGING_MODEL_VERIFIED`; direct smoke returned `4` |

One-task constrained staging container smokes passed for all four supplied IDs with official output shape preserved.

No API key is stored in source, Dockerfiles, image environment, benchmark files, or documentation.

## Token Accounting

Ollama Cloud staging token metadata is recorded only as development comparison data:

```text
staging_remote_prompt_tokens
staging_remote_completion_tokens
staging_remote_total_tokens
official_fireworks_token_score=NOT_MEASURED
```

Do not describe Ollama Cloud staging measurements as official competition evidence.
