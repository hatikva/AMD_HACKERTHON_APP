from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from .env import load_dotenv

load_dotenv()

from .pipeline import (
    VERSION_5_LOCAL_PROVIDER,
    VERSION_6_LOCAL_PROVIDER,
    VERSION_6_PRODUCTION_PROVIDER,
    VERSION_6_STAGING_PROVIDER,
    preflight,
    record_to_json,
    run_scenario,
    run_tasks_file,
)


def optional_command(command: list[str]) -> str:
    try:
        return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout.strip()
    except FileNotFoundError:
        return "not_found"


def cmd_preflight(_: argparse.Namespace) -> int:
    data = preflight()
    probes = {
        "kernel": optional_command(["uname", "-a"]),
        "pid1": optional_command(["ps", "-p", "1", "-o", "comm="]),
        "docker": optional_command(["docker", "--version"]),
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


def cmd_run_submission(args: argparse.Namespace) -> int:
    record = run_tasks_file(
        input_path=Path(args.input),
        output_path=Path(args.output),
        provider_override=args.provider,
    )
    print(record_to_json({"status": "completed", "result_path": record["result_path"], "task_count": record["task_count"]}))
    return 0


def cmd_validate_benchmark(args: argparse.Namespace) -> int:
    from .benchmarks import load_category_benchmark

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
    from .benchmarks import BENCHMARK_SUITE_ID, run_category_benchmark

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


def cmd_build_version5_analytics(args: argparse.Namespace) -> int:
    from .analytics import write_version5_analytics

    payload = write_version5_analytics(results_dir=Path(args.results_dir), output_path=Path(args.output))
    print(
        record_to_json(
            {
                "schema": payload["schema"],
                "benchmark_suite": payload["benchmark_suite"],
                "benchmark_hash": payload["benchmark_hash"],
                "source_result_files": payload["source_result_files"],
                "output": args.output,
                "authorization_registry_mutated": payload["authorization_registry_mutated"],
                "local_jurisdictions_promoted": payload["local_jurisdictions_promoted"],
                "status": "completed",
            }
        )
    )
    return 0


def cmd_build_version6_analytics(args: argparse.Namespace) -> int:
    from .analytics import write_version6_analytics

    payload = write_version6_analytics(results_dir=Path(args.results_dir), output_path=Path(args.output))
    print(
        record_to_json(
            {
                "schema": payload["schema"],
                "source_result_files": payload["source_result_files"],
                "output": args.output,
                "deduced_analytics_source": payload["deduced_analytics"]["source"],
                "status": "completed",
            }
        )
    )
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    from .ui import run as run_ui

    run_ui(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amd-router")
    subcommands = parser.add_subparsers(dest="command", required=True)
    providers = [
        "mock",
        "fireworks",
        "ollama-demo",
        "version5",
        VERSION_5_LOCAL_PROVIDER,
        VERSION_6_LOCAL_PROVIDER,
        VERSION_6_PRODUCTION_PROVIDER,
        VERSION_6_STAGING_PROVIDER,
        "llama-cpp",
    ]
    canonical_benchmark_path = "benchmarks/categories/version5_local_category_benchmarks_v2.json"
    benchmark_suite_id = "version5-category-benchmark-v2"

    preflight_parser = subcommands.add_parser("preflight")
    preflight_parser.set_defaults(func=cmd_preflight)

    run_parser = subcommands.add_parser("run-scenario")
    run_parser.add_argument("--scenario", default="classification-basic")
    run_parser.add_argument("--profile", default=os.environ.get("ROUTING_PROFILE", "version-3-work-jurisdiction"))
    run_parser.add_argument("--provider", choices=providers, default=None)
    run_parser.add_argument("--run-dir", default=None)
    run_parser.set_defaults(func=cmd_run_scenario)

    tasks_parser = subcommands.add_parser("run-tasks")
    tasks_parser.add_argument("--input", default="/input/tasks.json")
    tasks_parser.add_argument("--output", default="/output/results.json")
    tasks_parser.add_argument("--provider", choices=providers, default=None)
    tasks_parser.set_defaults(func=cmd_run_tasks)

    submission_parser = subcommands.add_parser("run-submission")
    submission_parser.add_argument("--input", default="/input/tasks.json")
    submission_parser.add_argument("--output", default="/output/results.json")
    submission_parser.add_argument("--provider", choices=providers, default=None)
    submission_parser.set_defaults(func=cmd_run_submission)

    validate_benchmark_parser = subcommands.add_parser("validate-category-benchmark")
    validate_benchmark_parser.add_argument("--suite", default=canonical_benchmark_path)
    validate_benchmark_parser.set_defaults(func=cmd_validate_benchmark)

    benchmark_parser = subcommands.add_parser("benchmark-categories")
    benchmark_parser.add_argument("--suite", default=canonical_benchmark_path)
    benchmark_parser.add_argument("--provider", choices=providers, default="mock")
    benchmark_parser.add_argument("--model", default=None)
    benchmark_parser.add_argument("--output", default=None)
    benchmark_parser.add_argument("--suite-id", default=benchmark_suite_id, help="Expected suite identifier for operator clarity.")
    benchmark_parser.set_defaults(func=cmd_benchmark_categories)

    analytics_parser = subcommands.add_parser("build-version5-analytics")
    analytics_parser.add_argument("--results-dir", default="qualification/results")
    analytics_parser.add_argument("--output", default="docs/version5_authority_analytics.json")
    analytics_parser.set_defaults(func=cmd_build_version5_analytics)

    analytics6_parser = subcommands.add_parser("build-version6-analytics")
    analytics6_parser.add_argument("--results-dir", default="qualification/results")
    analytics6_parser.add_argument("--output", default="docs/version6_submission_analytics.json")
    analytics6_parser.set_defaults(func=cmd_build_version6_analytics)

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
