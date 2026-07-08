# Routing Policy

Use Work Jurisdiction routing.

The runtime control plane should classify task family, choose a jurisdiction, select a compact prompt and answer schema, pack available evidence, validate deterministically, and repair structurally when safe.

Final-compatible semantic inference goes through Fireworks using `FIREWORKS_BASE_URL` and models sourced from `ALLOWED_MODELS`.

The optional `ollama-demo` provider is only for Version 3 demonstration with `qwen2.5-coder:3b`; it is not a final-mode route.
