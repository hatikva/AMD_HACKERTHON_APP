#!/usr/bin/env bash
set -Eeuo pipefail

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama command not found; nothing to stop"
  exit 0
fi

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-active --quiet ollama 2>/dev/null; then
  systemctl --user stop ollama
elif command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet ollama 2>/dev/null; then
  sudo systemctl stop ollama
else
  pkill -f 'ollama serve' 2>/dev/null || true
fi

if command -v ss >/dev/null 2>&1 && ss -ltn '( sport = :11434 )' | grep -q 11434; then
  echo "port 11434 is still listening after Ollama stop attempt" >&2
  exit 1
fi

echo "Ollama is not listening on 11434"
