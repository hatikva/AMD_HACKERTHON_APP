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

- `version6-staging`: production-shaped development target with a visibly separate staging fallback endpoint.
- `version6-production`: official submission target with Fireworks fallback only.

Both targets bundle CPU-only Ollama and `nemotron-3-nano:4b`. Local inference inside the container counts as zero judged Fireworks tokens. Any production fallback must use `FIREWORKS_BASE_URL`, `FIREWORKS_API_KEY`, and `ALLOWED_MODELS` from the runtime environment.

The production image must not contain UI assets, benchmark answer files, evaluator fixtures, grading keys, qualification reports, or a production `.env` file.
