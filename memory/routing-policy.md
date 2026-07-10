# Routing Policy

Use Work Jurisdiction routing.

The runtime control plane should classify task family, choose a jurisdiction, select a compact prompt and answer schema, pack available evidence, validate deterministically, and repair structurally when safe.

Final-compatible semantic inference goes through Fireworks using `FIREWORKS_BASE_URL` and models sourced from `ALLOWED_MODELS`, except for Version 5 jurisdictions explicitly authorized for the certified local Ollama runtime.

The optional `ollama-demo` provider is only for Version 3 demonstration with `qwen2.5-coder:3b`; it is not a final-mode route.

The Version 5 local runtime provider identity is `version5-ollama` with `nemotron-3-nano:4b`. Runtime certification does not imply jurisdiction certification; `LOCAL_CERTIFIED` still requires benchmark and validation evidence.
