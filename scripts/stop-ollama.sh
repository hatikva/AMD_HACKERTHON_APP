#!/usr/bin/env bash
set -Eeuo pipefail

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama command not found; nothing to stop"
  exit 0
fi

if command -v systemctl >/dev/null 2>&1; then
  for unit in ollama.service ollama-host.service; do
    if systemctl --user list-unit-files "$unit" 2>/dev/null | grep -q "$unit"; then
      systemctl --user disable --now "$unit" 2>/dev/null || systemctl --user stop "$unit" 2>/dev/null || true
    fi
  done

  if systemctl list-unit-files ollama.service 2>/dev/null | grep -q ollama.service; then
    if command -v sudo >/dev/null 2>&1; then
      sudo systemctl disable --now ollama.service 2>/dev/null || sudo systemctl stop ollama.service 2>/dev/null || true
    else
      systemctl stop ollama.service 2>/dev/null || true
    fi
  fi
fi

if pgrep -x ollama >/dev/null 2>&1 || pgrep -f 'ollama serve' >/dev/null 2>&1; then
  pkill -x ollama 2>/dev/null || true
  pkill -f 'ollama serve' 2>/dev/null || true
fi

for _ in $(seq 1 20); do
  if ! command -v ss >/dev/null 2>&1 || ! ss -ltn '( sport = :11434 )' | grep -q 11434; then
    echo "Ollama is not listening on 11434"
    exit 0
  fi
  sleep 1
done

echo "port 11434 is still listening after Ollama stop attempt" >&2
pgrep -a ollama >&2 || true
exit 1
