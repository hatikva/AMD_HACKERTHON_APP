#!/usr/bin/env bash
set -euo pipefail

ollama serve &
ollama_pid="$!"

cleanup() {
  kill "$ollama_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python - <<'PY'
import json
import time
import urllib.request

deadline = time.time() + 30
last_error = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            json.load(response)
        break
    except Exception as exc:
        last_error = exc
        time.sleep(0.25)
else:
    raise SystemExit(f"ollama did not become ready: {last_error}")
PY

exec "$@"
