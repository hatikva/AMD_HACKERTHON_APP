#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [
    "Qwen3-4B-Instruct-2507-GGUF",
    "Phi-4-mini-instruct-GGUF",
    "LFM2.5-1.2B-Instruct-GGUF",
]


def run(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def list_models() -> dict[str, str]:
    result = run(["docker", "compose", "-f", "compose.dev.yml", "exec", "lemonade", "./lemonade-server", "list"], timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stdout)

    models: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith((">", "Model Name", "-", "\u001b")):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] in {"Yes", "No"}:
            models[parts[0]] = "downloaded" if parts[1] == "Yes" else "available_not_downloaded"
    return models


def pull_model(model_id: str) -> dict[str, str | int]:
    timeout = int(os.environ.get("LEMONADE_MODEL_PULL_TIMEOUT_SECONDS", "3600"))
    result = run(
        ["docker", "compose", "-f", "compose.dev.yml", "exec", "lemonade", "./lemonade-server", "pull", model_id],
        timeout=timeout,
    )
    return {
        "returncode": result.returncode,
        "output_tail": "\n".join(result.stdout.splitlines()[-20:]),
    }


def main() -> int:
    before = list_models()
    statuses: list[dict[str, object]] = []

    for model_id in CANDIDATES:
        current = before.get(model_id)
        if current == "downloaded":
            statuses.append({"model_id": model_id, "status": "downloaded", "action": "skipped"})
            continue
        if current is None:
            statuses.append({
                "model_id": model_id,
                "status": "registry_mismatch",
                "action": "not_pulled",
                "note": "Exact ID not present in Lemonade registry output; no substitution performed.",
            })
            continue

        pull = pull_model(model_id)
        after_pull = list_models().get(model_id)
        statuses.append({
            "model_id": model_id,
            "status": after_pull or "unknown_after_pull",
            "action": "pull_attempted",
            "pull": pull,
        })

    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": statuses,
        "complete_for_available_exact_ids": all(
            row["status"] in {"downloaded", "registry_mismatch"} for row in statuses
        ),
    }
    destination = ROOT / "audit/model-acquisition-status.json"
    destination.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(f"model acquisition timed out: {exc}", file=sys.stderr)
        raise SystemExit(124)
    except Exception as exc:
        print(f"model acquisition failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
