# Model Registry Status

Observed through:

```bash
docker compose -f compose.dev.yml exec lemonade ./lemonade-server list
```

## Candidate Models

| Model ID | Status | Notes |
| --- | --- | --- |
| `Qwen3-4B-Instruct-2507-GGUF` | downloaded, unloadable | Lemonade lists the model as downloaded, but llama.cpp failed to load the cache path as a GGUF file during local benchmark. |
| `Phi-4-mini-instruct-GGUF` | downloaded | Exact requested ID is available and downloaded. |
| `LFM2.5-1.2B-Instruct-GGUF` | registry mismatch | Exact requested ID was not listed by Lemonade on 2026-06-25. |
| `nemotron-3-nano:4b` | selected for Version 5 | GGUF observed in the Ollama backup store, size `2,837,586,496` bytes, SHA-256 `527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970`; not yet locally certified for any jurisdiction. |

Do not silently substitute `LFM2-1.2B-GGUF` or any other ID for `LFM2.5-1.2B-Instruct-GGUF`. A substitution requires an explicit organiser/model-source decision.
