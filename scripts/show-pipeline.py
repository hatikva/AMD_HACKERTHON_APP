#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    pipeline = json.loads((ROOT / "audit/pipeline.json").read_text(encoding="utf-8"))
    print(pipeline["principle"])
    for stage in pipeline["stages"]:
        print(f"{stage['id']}: {stage['status']}")
        print(f"  command: {stage['command']}")
        if "next_action" in stage:
            print(f"  next_action: {stage['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
