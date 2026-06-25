# Container Packaging

Development and submission packaging are separate concerns.

## Development

`compose.dev.yml` uses named volumes so candidate models and Lemonade backend state are not repeatedly downloaded:

- `lemonade-cache`
- `lemonade-llama`
- `lemonade-recipe`

These volumes are not part of the image. A container that depends on them is not self-contained.

## Submission

The final submission must not depend on host bind mounts or pre-existing model volumes. Do not commit model weights to Git.

Only one selected local model should be embedded or downloaded for the final image after benchmark evidence identifies the recommended model/profile. Runtime downloads are smaller but require evaluator network access. Build-time embedding increases image size but can support offline startup if tested honestly.

## Offline Test Requirement

Before claiming a submission image is self-contained:

1. Build the image from a clean context.
2. Run it without model volumes or bind mounts.
3. Disable outbound network access.
4. Confirm the selected model loads and serves a non-empty response.

Compose YAML alone does not prove scoring accepts multiple containers or that weights are self-contained.
