from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from .env import load_dotenv

load_dotenv()

from .benchmarks import CANONICAL_BENCHMARK_PATH, BENCHMARK_SUITE_ID, load_category_benchmark, run_category_benchmark
from .pipeline import preflight, record_to_json, run_scenario, run_tasks_file
from .ui import run as run_ui


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
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )
    print(record_to_json(record))
    return 0


def cmd_run_tasks(args: argparse.Namespace) -> int:
    record = run_tasks_file(
        input_path=Path(args.input),
        output_path=Path(args.output),
        provider_override=args.provider,
    )
    print(record_to_json(record))
    return 0


def cmd_validate_benchmark(args: argparse.Namespace) -> int:
    suite = load_category_benchmark(Path(args.suite))
    print(
        json.dumps(
            {
                "benchmark_suite": suite.suite_id,
                "benchmark_hash": suite.content_hash,
                "path": str(suite.path),
                "schema": suite.payload["schema"],
                "category_count": len(suite.payload["categories"]),
                "task_count": len(suite.tasks),
                "status": "valid",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_benchmark_categories(args: argparse.Namespace) -> int:
    if args.suite_id != BENCHMARK_SUITE_ID:
        raise SystemExit(f"unsupported benchmark suite id: {args.suite_id}")
    result = run_category_benchmark(
        suite_path=Path(args.suite),
        provider=args.provider,
        model=args.model,
        output_path=Path(args.output) if args.output else None,
    )
    print(record_to_json(result))
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    run_ui(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amd-router")
    subcommands = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subcommands.add_parser("preflight")
    preflight_parser.set_defaults(func=cmd_preflight)

    run_parser = subcommands.add_parser("run-scenario")
    run_parser.add_argument("--scenario", default="classification-basic")
    run_parser.add_argument("--profile", default=os.environ.get("ROUTING_PROFILE", "version-3-work-jurisdiction"))
    run_parser.add_argument("--provider", choices=["mock", "fireworks", "ollama-demo", "version5"], default=None)
    run_parser.add_argument("--run-dir", default=None)
    run_parser.set_defaults(func=cmd_run_scenario)

    tasks_parser = subcommands.add_parser("run-tasks")
    tasks_parser.add_argument("--input", default="/input/tasks.json")
    tasks_parser.add_argument("--output", default="/output/results.json")
    tasks_parser.add_argument("--provider", choices=["mock", "fireworks", "ollama-demo", "version5"], default=None)
    tasks_parser.set_defaults(func=cmd_run_tasks)

    validate_benchmark_parser = subcommands.add_parser("validate-category-benchmark")
    validate_benchmark_parser.add_argument("--suite", default=str(CANONICAL_BENCHMARK_PATH))
    validate_benchmark_parser.set_defaults(func=cmd_validate_benchmark)

    benchmark_parser = subcommands.add_parser("benchmark-categories")
    benchmark_parser.add_argument("--suite", default=str(CANONICAL_BENCHMARK_PATH))
    benchmark_parser.add_argument("--provider", choices=["mock", "fireworks", "version5", "llama-cpp"], default="mock")
    benchmark_parser.add_argument("--model", default=None)
    benchmark_parser.add_argument("--output", default=None)
    benchmark_parser.add_argument("--suite-id", default=BENCHMARK_SUITE_ID, help="Expected suite identifier for operator clarity.")
    benchmark_parser.set_defaults(func=cmd_benchmark_categories)

    ui_parser = subcommands.add_parser("ui")
    ui_parser.add_argument("--host", default=os.environ.get("UI_HOST", "127.0.0.1"))
    ui_parser.add_argument("--port", type=int, default=int(os.environ.get("UI_PORT", "18083")))
    ui_parser.set_defaults(func=cmd_ui)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
