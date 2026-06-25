# Routing Policy

Use accuracy-first difficulty routing. Smaller local models are selected only when the task falls within their measured reliable threshold.

Escalate to Fireworks when task difficulty exceeds the local threshold, router confidence is too low, decisive context is omitted, or local validation fails.
