# Model Registry Status

Observed through:

```bash
docker compose -f compose.dev.yml exec lemonade ./lemonade-server list
```

## Seed Models

| Model ID | Status | Notes |
| --- | --- | --- |
| `Qwen3-4B-Instruct-2507-GGUF` | downloaded, unloadable | Lemonade lists the model as downloaded, but llama.cpp failed to load the cache path as a GGUF file during local benchmark. |
| `Phi-4-mini-instruct-GGUF` | downloaded | Seed ID is available, downloaded, and benchmarkable. |
| `LFM2.5-1.2B-Instruct-GGUF` | registry mismatch | Seed ID was not listed by Lemonade on 2026-06-25. |

These are seed models from the original prompt, not required IDs. Do not report `LFM2-1.2B-GGUF` or any other model as `LFM2.5-1.2B-Instruct-GGUF`. New local models can be benchmarked under their own identities and size tiers.
