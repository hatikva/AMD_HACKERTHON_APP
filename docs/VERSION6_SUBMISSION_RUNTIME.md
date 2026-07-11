# Version 6 Submission Runtime

Version 6 is the confirmed AMD Developer Hackathon ACT II Track 1 submission path for team `team-2168`.

The submission runtime is batch-only:

- reads `/input/tasks.json` on container startup;
- requires a top-level JSON array of records containing only `task_id` and `prompt`;
- writes `/output/results.json`;
- writes a top-level JSON array of records containing only `task_id` and `answer`;
- preserves task IDs and input order;
- exits `0` after a successful batch and non-zero on failure;
- does not start a UI, wait for interactive input, or require a manual API request.

The two submission targets share the same code path and bundled local runtime:

- `version6-staging`: production-shaped development target with a visibly separate Ollama Cloud staging fallback. It is `NOT_FOR_SUBMISSION`.
- `version6-production`: official submission target with Fireworks fallback only.

Both targets bundle CPU-only Ollama and `nemotron-3-nano:4b`. Local inference inside the container counts as zero judged Fireworks tokens. Any production fallback must use `FIREWORKS_BASE_URL`, `FIREWORKS_API_KEY`, and `ALLOWED_MODELS` from the runtime environment.

The production image must not contain UI assets, benchmark answer files, evaluator fixtures, grading keys, qualification reports, or a production `.env` file.

## Production Remote Policy

Production remote fallback is Fireworks-only:

- `FIREWORKS_BASE_URL` is the official remote base URL.
- `FIREWORKS_API_KEY` is supplied by the judging harness.
- `ALLOWED_MODELS` is the harness-provided set of permitted Fireworks models.

Production must not use `OLLAMA_API_KEY`, `OLLAMA_CLOUD_BASE_URL`, `STAGING_ALLOWED_MODELS`, `STAGING_INFERENCE_MODEL`, or `STAGING_REMOTE_PROVIDER`.

## Version 6 Staging Ollama Cloud Policy

Staging uses Ollama Cloud only when all guard variables are explicit:

```text
VERSION6_REMOTE_FALLBACK=staging
STAGING_REMOTE_PROVIDER=ollama-cloud
OLLAMA_API_KEY=<supplied securely at runtime>
OLLAMA_CLOUD_BASE_URL=https://ollama.com
STAGING_ALLOWED_MODELS=minimax-m3:cloud,nemotron-3-super:cloud,gpt-oss:20b-cloud,gemma4:31b-cloud
STAGING_INFERENCE_MODEL=<one supplied staging model id>
```

`STAGING_ALLOWED_MODELS` is a locally controlled development candidate list. It is not equivalent to production `ALLOWED_MODELS` and must not mutate production authorization registries.

The native Ollama Cloud adapter posts to:

```text
POST /api/chat
```

It does not use the OpenAI-compatible `/chat/completions` path. Staging telemetry is written under `/output/audit` by default and official `/output/results.json` still contains only `task_id` and `answer`.

Ollama Cloud token metadata is recorded only as staging comparison data:

```text
staging_remote_prompt_tokens
staging_remote_completion_tokens
staging_remote_total_tokens
official_fireworks_token_score=NOT_MEASURED
```

Do not treat Ollama Cloud measurements as judged Fireworks tokens.

## Verified Staging Model Mappings

The staging candidate identifiers were checked against Ollama Cloud `/api/tags` on 2026-07-11. The API-visible names omit the supplied cloud suffixes:

| Supplied ID | API model ID | Status |
| --- | --- | --- |
| `minimax-m3:cloud` | `minimax-m3` | direct smoke returned `4` |
| `nemotron-3-super:cloud` | `nemotron-3-super` | listed by `/api/tags`; direct smoke timed out |
| `gpt-oss:20b-cloud` | `gpt-oss:20b` | direct smoke returned `4` |
| `gemma4:31b-cloud` | `gemma4:31b` | direct smoke returned `4` |

No API key is stored in source, image layers, benchmark files, or documentation.
