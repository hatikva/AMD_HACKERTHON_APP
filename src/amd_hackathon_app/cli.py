from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from .pipeline import preflight, record_to_json, run_scenario
from .web import run as run_web


def cmd_preflight(_: argparse.Namespace) -> int:
    data = preflight()
    probes = {
        "kernel": subprocess.run(["uname", "-a"], text=True, stdout=subprocess.PIPE, check=False).stdout.strip(),
        "pid1": subprocess.run(["ps", "-p", "1", "-o", "comm="], text=True, stdout=subprocess.PIPE, check=False).stdout.strip(),
        "docker": subprocess.run(["docker", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip(),
    }
    print(json.dumps({**data, "environment": probes}, indent=2, sort_keys=True))
    return 0


def cmd_run_scenario(args: argparse.Namespace) -> int:
    record = run_scenario(
        scenario_id=args.scenario,
        profile_id=args.profile,
        provider_override=args.provider,
        model_override=args.model,
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )
    print(record_to_json(record))
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    run_web(args.host, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amd-router")
    subcommands = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subcommands.add_parser("preflight")
    preflight_parser.set_defaults(func=cmd_preflight)

    run_parser = subcommands.add_parser("run-scenario")
    run_parser.add_argument("--scenario", default="classification-basic")
    run_parser.add_argument("--profile", default=os.environ.get("ROUTING_PROFILE", "balanced-local-first"))
    run_parser.add_argument("--provider", choices=["mock", "local", "fireworks", "ollama_cloud"], default=None)
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("--run-dir", default=None)
    run_parser.set_defaults(func=cmd_run_scenario)

    ui_parser = subcommands.add_parser("ui")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8765)
    ui_parser.set_defaults(func=cmd_ui)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
