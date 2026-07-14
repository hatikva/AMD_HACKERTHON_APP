# Container Packaging

This repository is now organized around the Version 7 production submission
runtime.

## Official Submission Image

Build the official image with:

```bash
docker build -f Dockerfile.submission -t amd-hackathon:version7-production .
```

`Dockerfile.submission` is intentionally aligned with `Dockerfile.version7`.
Both run the same entrypoint and the same production command:

```bash
amd-router run-version7-submission \
  --input /input/tasks.json \
  --output /output/results.json \
  --audit-log /output/audit.jsonl
```

The image embeds the selected local Ollama model payload from
`models/version5-ollama/`. The directory name is historical because the same
model artifact was qualified during earlier experiments; the promoted runtime is
Version 7.

## Runtime Contract

Version 7 expects:

- `/input/tasks.json` mounted read-only with the official task list;
- `/output` mounted writable for `results.json` and `audit.jsonl`;
- `FIREWORKS_API_KEY` supplied at runtime;
- no host model volume, no runtime model download, and no second service
  container.

The container starts exactly one local `ollama serve` child process, waits for
the embedded model to become available, validates that the Fireworks Kimi model
is enabled, and then runs the deterministic Version 7 scheduler.

## Routing Policy

Version 7 uses one canonical classifier and eight official categories:

- `CODE_GENERATION`: Fireworks Kimi, `max_tokens=1000`
- `FACTUAL`: Fireworks Kimi, `max_tokens=256`
- `LOGICAL`: Fireworks Kimi, `max_tokens=256`
- `MATH`: Fireworks Kimi, `max_tokens=400`
- `SENTIMENT`: Fireworks Kimi, `max_tokens=256`
- `CODE_DEBUGGING`: local Ollama, `max_tokens=1000`
- `NAMED_ENTITY_RECOGNITION`: local Ollama, `max_tokens=1000`
- `TEXT_SUMMARISATION`: local Ollama, `max_tokens=1000`

Classification is serial. The default scheduler classifies and routes every
task first, then starts answer generation. Fireworks tasks run with bounded
remote concurrency while local answer generation runs serially to protect the
embedded local model under the target CPU and memory envelope. Output order
always matches the input order.

Answer prompt policy is fixed in code. Wrappers are user-message prefixes, not
system prompts. Primary Fireworks calls use the raw official prompt except
`FACTUAL_KNOWLEDGE`, which uses the factual wrapper. Local Ollama answer
categories use their category wrappers. Fallback answer calls inherit the same
category prompt policy: factual fallback to Minimax keeps the factual wrapper,
and local-primary categories that fall back to Fireworks keep their category
wrapper.

## Verification

Run the local verification script before publishing a submission image:

```bash
scripts/verify-version7-image.sh amd-hackathon:version7-production
```

The verifier checks:

- image architecture and compressed size;
- embedded Ollama model availability;
- official category validation;
- Kimi availability enforcement;
- malformed-input failure behavior;
- missing-`FIREWORKS_API_KEY` failure behavior;
- no partial `results.json` on fatal startup or validation failures.

For release verification, also run an end-to-end mixed-category smoke using a
fake Fireworks-compatible endpoint and inspect `/output/audit.jsonl` for the
expected five remote answers and three local answers.

## Historical Packaging

Earlier Version 5 and Version 6 Dockerfiles, scripts, and benchmark artifacts
remain in the repository only as implementation evidence. They are not the
official submission runtime. New submission work should use
`Dockerfile.submission`, `Dockerfile.version7`, and `src/amd_hackathon_app/version7.py`.
