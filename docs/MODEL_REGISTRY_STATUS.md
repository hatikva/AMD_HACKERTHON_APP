# Model Registry Status

Observed through:

```bash
docker compose -f compose.dev.yml exec lemonade ./lemonade-server list
```

## Candidate Models

| Model ID | Status | Notes |
| --- | --- | --- |
| `Qwen3-4B-Instruct-2507-GGUF` | downloaded | Exact requested ID is available and downloaded. |
| `Phi-4-mini-instruct-GGUF` | available, not downloaded | Exact requested ID is available in the Lemonade registry. |
| `LFM2.5-1.2B-Instruct-GGUF` | registry mismatch | Exact requested ID was not listed by Lemonade on 2026-06-25. |

Do not silently substitute `LFM2-1.2B-GGUF` or any other ID for `LFM2.5-1.2B-Instruct-GGUF`. A substitution requires an explicit organiser/model-source decision.
