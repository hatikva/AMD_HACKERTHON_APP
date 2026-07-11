# Project Doctrine

The project targets AMD Developer Hackathon Track 1 as the Most Innovative Routing System.

Token efficiency comes from deterministic task-family handling, Work Jurisdiction routing, compact prompt construction, validation, repair, and Fireworks-compatible model selection.

Version 3 remains the demo architecture. Its `ollama-demo` provider is only for demo and development work.

Version 4 remains a valid Fireworks-only submission candidate: all semantic inference goes through `FIREWORKS_BASE_URL`, and final model IDs come from `ALLOWED_MODELS`.

Version 5 is a valid local-runtime submission candidate. It uses bundled CPU-only Ollama with `nemotron-3-nano:4b` through provider identity `version5-ollama`, with Fireworks fallback still routed through `FIREWORKS_BASE_URL` and model IDs from `ALLOWED_MODELS`.

Runtime certification does not imply Work Jurisdiction or category authorization. Local-first routing is allowed only after benchmark evidence is reviewed and promoted into authority records. Current benchmark analytics are reviewed evidence only and do not mutate runtime authorization.
