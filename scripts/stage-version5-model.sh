#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source_path="${1:-}"
if [[ -z "$source_path" ]]; then
  if [[ -e ".local/ollama-backup-gguf-import/backup-nemotron-3-nano-4b.gguf" ]]; then
    source_path=".local/ollama-backup-gguf-import/backup-nemotron-3-nano-4b.gguf"
  elif [[ -e "/mnt/g/ollama-models-backup-container/models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970" ]]; then
    source_path="/mnt/g/ollama-models-backup-container/models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970"
  else
    echo "nemotron-3-nano:4b GGUF source not found; pass the source path as the first argument" >&2
    exit 1
  fi
fi

destination="models/version5/nemotron-3-nano-4b.gguf"
expected_sha="527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970"
expected_size="2837586496"

mkdir -p "$(dirname "$destination")"
cp -L "$source_path" "$destination"

actual_sha="$(sha256sum "$destination" | awk '{print $1}')"
actual_size="$(stat -Lc '%s' "$destination")"

if [[ "$actual_sha" != "$expected_sha" ]]; then
  echo "unexpected GGUF sha256: $actual_sha" >&2
  exit 1
fi
if [[ "$actual_size" != "$expected_size" ]]; then
  echo "unexpected GGUF size: $actual_size" >&2
  exit 1
fi

printf 'staged %s (%s bytes, sha256:%s)\n' "$destination" "$actual_size" "$actual_sha"
