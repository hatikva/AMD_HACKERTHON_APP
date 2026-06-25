# Ollama GGUF Import

Lemonade can import raw GGUF files through `extra_models_dir`, but the Ollama model directory must not be treated as a directly supported Lemonade model store.

Current source check:

- Lemonade documents `extra_models_dir` as a recursive search path for GGUF LLM files.
- Lemonade also documents `models_dir="auto"` for sharing Hugging Face cache state across apps.
- A current Lemonade issue records that pointing `extra_models_dir` at an Ollama download tree does not load Ollama models reliably.
- Ollama manifests can reference raw GGUF model blobs under `~/.ollama/models/blobs/`.

## Project Rule

Ollama GGUF blobs may be used as explicit import/staging inputs for local-model benchmark expansion. The original prompt-supplied models are seed candidates, not required IDs.

Do not silently report an Ollama model as one of the seed models unless the identity actually matches:

- `Qwen3-4B-Instruct-2507-GGUF`
- `Phi-4-mini-instruct-GGUF`
- `LFM2.5-1.2B-Instruct-GGUF`

## Audit Command

```bash
python3 scripts/audit-ollama-gguf.py
```

This records manifest, blob, GGUF, seed-model-match, rough parameter tier, and exploratory benchmark eligibility evidence in:

```text
audit/ollama-gguf-import-status.json
```

Observed on 2026-06-25:

```text
manifest_model_layers: 12
gguf_model_blobs: 10
seed_model_id_matches: 0
small_under_4b: 4
mid_4b_to_under_7b: 3
large_7b_plus: 3
```

That means this checkout has reusable GGUF bytes in the Ollama cache. None currently matches the original seed model IDs, but the audited local models are valid exploratory benchmark candidates once staged through Lemonade and recorded as their own model identities.

To create local symlinks for a manual Lemonade `extra_models_dir` experiment:

```bash
python3 scripts/audit-ollama-gguf.py --stage
```

The stage directory is ignored by Git:

```text
.local/ollama-gguf-import/
```

Do not commit model blobs, staged links, or copied weights.
