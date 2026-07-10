#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT_DIR/models/version5-ollama"
OLLAMA_BIN="${OLLAMA_BIN:-/usr/local/bin/ollama}"
OLLAMA_LIB_DIR="${OLLAMA_LIB_DIR:-/usr/local/lib/ollama}"
OLLAMA_MODELS_DIR="${OLLAMA_MODELS_DIR:-/home/user/.ollama/models}"
MODEL_MANIFEST="$OLLAMA_MODELS_DIR/manifests/registry.ollama.ai/library/nemotron-3-nano/4b"

MODEL_DIGEST="527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970"
CONFIG_DIGEST="1c309ae5e93ede03f48f4bdbfd1b50d1780f2c3bcdc82f4569e20f0c33878db9"
LICENSE_DIGEST="355e036064fa9b3a96ce0cdbb69abe54f5c7ce0b6aa2c7d5f8ec8580b011c20e"
PARAMS_DIGEST="12e88b2a8727339b5a4a8b3e2d0d637ac1c61085b1072e77865f0c25d6e468eb"

if [[ ! -x "$OLLAMA_BIN" ]]; then
  echo "ollama binary not found or not executable: $OLLAMA_BIN" >&2
  exit 1
fi
if [[ ! -d "$OLLAMA_LIB_DIR" ]]; then
  echo "ollama library directory not found: $OLLAMA_LIB_DIR" >&2
  exit 1
fi
if [[ ! -f "$MODEL_MANIFEST" ]]; then
  echo "nemotron manifest not found: $MODEL_MANIFEST" >&2
  exit 1
fi

rm -rf "$DEST"
install -d "$DEST/bin" "$DEST/lib/ollama" "$DEST/models/blobs" "$DEST/models/manifests/registry.ollama.ai/library/nemotron-3-nano"
install -m 0755 "$OLLAMA_BIN" "$DEST/bin/ollama"

cp -a "$OLLAMA_LIB_DIR"/lib*.so* "$DEST/lib/ollama/"
cp -a "$OLLAMA_LIB_DIR"/llama-server "$DEST/lib/ollama/"
cp -a "$OLLAMA_LIB_DIR"/llama-quantize "$DEST/lib/ollama/"

cp "$MODEL_MANIFEST" "$DEST/models/manifests/registry.ollama.ai/library/nemotron-3-nano/4b"
cp "$OLLAMA_MODELS_DIR/blobs/sha256-$CONFIG_DIGEST" "$DEST/models/blobs/sha256-$CONFIG_DIGEST"
cp "$OLLAMA_MODELS_DIR/blobs/sha256-$MODEL_DIGEST" "$DEST/models/blobs/sha256-$MODEL_DIGEST"
cp "$OLLAMA_MODELS_DIR/blobs/sha256-$LICENSE_DIGEST" "$DEST/models/blobs/sha256-$LICENSE_DIGEST"
cp "$OLLAMA_MODELS_DIR/blobs/sha256-$PARAMS_DIGEST" "$DEST/models/blobs/sha256-$PARAMS_DIGEST"

actual_sha="$(sha256sum "$DEST/models/blobs/sha256-$MODEL_DIGEST" | awk '{print $1}')"
if [[ "$actual_sha" != "$MODEL_DIGEST" ]]; then
  echo "unexpected model sha256: $actual_sha" >&2
  exit 1
fi

du -sh "$DEST"
find "$DEST" -maxdepth 3 -type f -printf '%p %s\n' | sort
