# Fireworks Model Resources

Observed on 2026-07-08 from Fireworks model pages.

These values document the current resource names for the Track 1 planning seed list. Runtime selection must still use the exact `ALLOWED_MODELS` value supplied by the environment.

| Seed ID | Fireworks resource name | Serverless status observed |
| --- | --- | --- |
| `minimax-m3` | `accounts/fireworks/models/minimax-m3` | supported |
| `kimi-k2p7-code` | `accounts/fireworks/models/kimi-k2p7-code` | supported |
| `gemma-4-31b-it` | `accounts/fireworks/models/gemma-4-31b-it` | not supported |
| `gemma-4-26b-a4b-it` | `accounts/fireworks/models/gemma-4-26b-a4b-it` | not supported |
| `gemma-4-31b-it-nvfp4` | `accounts/fireworks/models/gemma-4-31b-it-nvfp4` | not supported |

Do not hardcode this list as the final model set. The scoring environment may provide a different `ALLOWED_MODELS` value.
