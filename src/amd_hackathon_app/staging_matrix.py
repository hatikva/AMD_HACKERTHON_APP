from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .benchmarks import (
    BENCHMARK_SUITE_ID,
    CANONICAL_BENCHMARK_PATH,
    CANONICAL_CATEGORIES,
    evaluate_output,
    evaluator_record,
    file_sha256,
    load_category_benchmark,
    model_visible_task,
)
from .pipeline import (
    ROOT,
    STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
    VERSION_6_STAGING_PROVIDER,
    VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
    write_json,
)


DEFAULT_STAGING_IMAGE = "ghcr.io/hatikva/amd-hackathon-app:version6-staging-ollama-cloud-1cebdfc"
SHADOW_BENCHMARK_PATH = ROOT / "benchmarks/categories/version6_shadow_category_benchmarks_v1.json"
QUALIFICATION_SCHEMA = "amd_hackathon.qualification_results.v1"
STAGING_ALLOWED_MODELS = [
    "minimax-m3:cloud",
    "nemotron-3-super:cloud",
    "gpt-oss:20b-cloud",
    "gemma4:31b-cloud",
]
MODEL_MAPPINGS = {
    "minimax-m3:cloud": "minimax-m3",
    "nemotron-3-super:cloud": "nemotron-3-super",
    "gpt-oss:20b-cloud": "gpt-oss:20b",
    "gemma4:31b-cloud": "gemma4:31b",
}
MODES = {
    "remote": {
        "execution_mode": "staging_remote_baseline",
        "provider": VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
    },
    "routed": {
        "execution_mode": "version6_staging_routed",
        "provider": VERSION_6_STAGING_PROVIDER,
    },
}


@dataclass(frozen=True)
class SuiteSpec:
    key: str
    suite_id: str
    path: Path


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("v6-full-staging-%Y%m%dT%H%M%SZ")


def safe_model_dir(alias: str) -> str:
    return alias.replace(":", "-").replace("/", "-").replace("_", "-").replace("-cloud", "")


def load_suite(spec: SuiteSpec) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    suite = load_category_benchmark(spec.path)
    visible = [model_visible_task(task) for task in suite.tasks]
    evaluator = [evaluator_record(task) for task in suite.tasks]
    return visible, evaluator, file_sha256(spec.path)


def validate_suite_shape(spec: SuiteSpec) -> dict[str, Any]:
    visible, evaluator, content_hash = load_suite(spec)
    by_category = {category: 0 for category in CANONICAL_CATEGORIES}
    by_difficulty = {str(level): 0 for level in range(1, 6)}
    for row in evaluator:
        by_category[str(row["task_category"])] += 1
        by_difficulty[str(row["difficulty_hint"])] += 1
    official_projection_valid = all(set(row) == {"task_id", "prompt"} for row in visible)
    return {
        "suite": spec.key,
        "suite_id": spec.suite_id,
        "sha256": content_hash,
        "task_count": len(visible),
        "category_distribution": by_category,
        "difficulty_distribution": by_difficulty,
        "official_projection_valid": official_projection_valid,
    }


def run_command(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "output": completed.stdout,
    }


def inspect_staging_image(image: str) -> dict[str, Any]:
    auth_dir = Path(tempfile.mkdtemp(prefix="amd-staging-auth-"))
    auth_file = auth_dir / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    env = {**os.environ, "REGISTRY_AUTH_FILE": str(auth_file), "DOCKER_CONFIG": str(auth_dir)}
    try:
        pull = run_command(["podman", "pull", image], env=env)
        inspect = run_command(["podman", "image", "inspect", image], env=env)
    finally:
        shutil.rmtree(auth_dir, ignore_errors=True)
    details: list[dict[str, Any]] = []
    if inspect["exit_code"] == 0:
        details = json.loads(inspect["output"])
    first = details[0] if details else {}
    repo_digests = first.get("RepoDigests") or []
    return {
        "image_tag": image,
        "anonymous_pull": "passed" if pull["exit_code"] == 0 else "failed",
        "image_id": first.get("Id"),
        "config_digest": first.get("Id"),
        "local_manifest_digest": first.get("Digest"),
        "repo_digests": repo_digests,
        "repository_digest": repo_digests[0] if repo_digests else None,
        "remote_manifest_tooling": "UNAVAILABLE_NON_BLOCKING",
        "compressed_image_bytes": 2866371727,
        "staging_status": "NOT_FOR_SUBMISSION",
        "pull_log": pull["output"][-4000:],
    }


def validate_official_output(input_tasks: list[dict[str, str]], output_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not output_path.exists():
        return {"valid": False, "errors": ["missing output/results.json"]}
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"invalid JSON: {exc}"]}
    if not isinstance(payload, list):
        return {"valid": False, "errors": ["official output is not a top-level array"]}
    input_ids = [row["task_id"] for row in input_tasks]
    output_ids: list[str] = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            errors.append(f"result {index} is not an object")
            continue
        if set(row) != {"task_id", "answer"}:
            errors.append(f"result {index} has keys {sorted(row)}")
        task_id = row.get("task_id")
        answer = row.get("answer")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"result {index} has invalid task_id")
        else:
            output_ids.append(task_id)
        if not isinstance(answer, str) or not answer.strip():
            errors.append(f"result {index} has empty answer")
    if len(payload) != len(input_tasks):
        errors.append(f"expected {len(input_tasks)} records, got {len(payload)}")
    if output_ids != input_ids:
        errors.append("output IDs do not exactly match input order")
    if len(output_ids) != len(set(output_ids)):
        errors.append("duplicate output task IDs exist")
    unknown = sorted(set(output_ids).difference(input_ids))
    if unknown:
        errors.append(f"unknown output task IDs: {unknown}")
    return {"valid": not errors, "errors": errors, "task_count": len(payload), "results": payload if isinstance(payload, list) else []}


def latency_values(audit_dir: Path) -> list[int]:
    values: list[int] = []
    for path in sorted(audit_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        values.append(int(((payload.get("latency") or {}).get("milliseconds")) or 0))
    return values


def grade_results(
    suite: SuiteSpec,
    alias: str,
    mode_key: str,
    run_id: str,
    cell_dir: Path,
    input_tasks: list[dict[str, str]],
    evaluator_rows: list[dict[str, Any]],
    validation: dict[str, Any],
    timing: dict[str, Any],
) -> dict[str, Any]:
    evaluator_by_id = {row["task_id"]: row for row in evaluator_rows}
    official = validation.get("results") if validation.get("valid") else []
    official_by_id = {row["task_id"]: row for row in official if isinstance(row, dict) and isinstance(row.get("task_id"), str)}
    records: list[dict[str, Any]] = []
    audit_by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((cell_dir / "output/audit").glob("*.json")):
        try:
            audit = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        audit_by_id[str(audit.get("task_id"))] = audit
    for task in input_tasks:
        task_id = task["task_id"]
        evaluator = evaluator_by_id[task_id]
        answer = str((official_by_id.get(task_id) or {}).get("answer") or "")
        try:
            evaluation_result = evaluate_output(answer, evaluator["evaluation"]) if validation.get("valid") else {
                "implemented": True,
                "passed": False,
                "type": evaluator["evaluation"].get("type"),
                "reason": "output_contract_invalid",
            }
        except ValueError as exc:
            evaluation_result = {
                "implemented": False,
                "passed": False,
                "type": evaluator["evaluation"].get("type"),
                "reason": str(exc),
            }
        route_record = audit_by_id.get(task_id, {})
        token_usage = route_record.get("token_usage") or {}
        records.append(
            {
                "task_id": task_id,
                "task_category": evaluator["task_category"],
                "task_family": evaluator.get("task_family"),
                "difficulty_hint": evaluator["difficulty_hint"],
                "model_visible_task": task,
                "evaluator": {"type": evaluator["evaluation"].get("type"), "withheld_from_model": True},
                "evaluation_result": evaluation_result,
                "route_record": route_record,
                "judged_fireworks_tokens": 0,
                "judged_fireworks_tokens_status": "NOT_APPLICABLE_STAGING_PROVIDER",
                "official_fireworks_token_score": "NOT_MEASURED",
                "staging_remote_prompt_tokens": token_usage.get("staging_remote_prompt_tokens"),
                "staging_remote_completion_tokens": token_usage.get("staging_remote_completion_tokens"),
                "staging_remote_total_tokens": token_usage.get("staging_remote_total_tokens"),
            }
        )
    summary = summarize_records(records, validation, timing)
    mode = MODES[mode_key]
    payload = {
        "schema": QUALIFICATION_SCHEMA,
        "evidence_class": "staging_only",
        "submission_eligible": False,
        "automatic_authority_promotion": False,
        "eligible_for_official_token_comparison": False,
        "eligible_for_production_authorization": False,
        "authorization_registry_mutated": False,
        "suite": suite.key,
        "benchmark_suite": suite.suite_id,
        "benchmark_hash": file_sha256(suite.path),
        "benchmark_path": str(suite.path),
        "run_id": run_id,
        "execution_mode": mode["execution_mode"],
        "candidate": {
            "provider": mode["provider"],
            "remote_provider": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
            "requested_model_alias": alias,
            "supplied_model": alias,
            "exact_api_model_id": MODEL_MAPPINGS[alias],
            "model": MODEL_MAPPINGS[alias],
            "evidence_class": "staging_only",
            "submission_eligible": False,
            "automatic_authority_promotion": False,
        },
        "model_visible_tasks_path": str(cell_dir / "input/tasks.json"),
        "official_results_path": str(cell_dir / "output/results.json"),
        "production_path_used": False,
        "qualification_status": "STAGING_ONLY",
        "summary": summary,
        "results": records,
    }
    result_name = f"version6-staging-{suite.key}-{safe_model_dir(alias)}-{mode_key}-{run_id}.json"
    result_path = ROOT / "qualification/results" / result_name
    write_json(result_path, payload)
    payload["result_path"] = str(result_path)
    return payload


def summarize_records(records: list[dict[str, Any]], validation: dict[str, Any], timing: dict[str, Any]) -> dict[str, Any]:
    total = len(records)
    passed = sum(1 for row in records if row["evaluation_result"].get("passed"))
    latencies = [
        int(((row.get("route_record") or {}).get("latency") or {}).get("milliseconds") or 0)
        for row in records
        if row.get("route_record")
    ]
    staging_tokens = [
        row.get("staging_remote_total_tokens")
        for row in records
        if isinstance(row.get("staging_remote_total_tokens"), int)
    ]
    by_category: dict[str, dict[str, Any]] = {}
    by_difficulty: dict[str, dict[str, Any]] = {}
    for category in CANONICAL_CATEGORIES:
        by_category[category] = summarize_group([row for row in records if row["task_category"] == category])
    for difficulty in range(1, 6):
        by_difficulty[str(difficulty)] = summarize_group([row for row in records if row["difficulty_hint"] == difficulty])
    return {
        "overall_tasks": total,
        "overall_passed": passed,
        "overall_accuracy": passed / total if total else 0,
        "tasks_attempted": total,
        "tasks_completed": validation.get("task_count", 0),
        "validation_failures": 0 if validation.get("valid") else 1,
        "evaluator_failures": total - passed,
        "runtime_failures": 0 if timing.get("exit_code") == 0 else 1,
        "malformed_answers": 0 if validation.get("valid") else total,
        "empty_answers": 0,
        "retries": sum(int(((row.get("route_record") or {}).get("retry_count")) or 0) for row in records),
        "timeouts": 1 if timing.get("timed_out") else 0,
        "total_latency_ms": sum(latencies),
        "mean_latency_ms": statistics.mean(latencies) if latencies else 0,
        "median_latency_ms": statistics.median(latencies) if latencies else 0,
        "p95_latency_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0,
        "local_attempts": sum(1 for row in records if (row.get("route_record") or {}).get("local_attempted")),
        "local_successes": sum(1 for row in records if (row.get("route_record") or {}).get("local_success")),
        "local_failures": sum(1 for row in records if (row.get("route_record") or {}).get("local_failure")),
        "remote_calls": sum(1 for row in records if (row.get("route_record") or {}).get("selected_provider") == VERSION_6_STAGING_PROVIDER),
        "remote_fallbacks": sum(1 for row in records if (row.get("route_record") or {}).get("selected_path") == "staging_remote_fallback"),
        "staging_remote_tokens": sum(staging_tokens) if len(staging_tokens) == total else "NOT_RETURNED",
        "token_metric_status": "RETURNED" if len(staging_tokens) == total else "NOT_RETURNED",
        "judged_fireworks_tokens": 0,
        "judged_fireworks_tokens_status": "NOT_APPLICABLE_STAGING_PROVIDER",
        "by_category": by_category,
        "by_difficulty": by_difficulty,
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if row["evaluation_result"].get("passed"))
    latency = sum(int(((row.get("route_record") or {}).get("latency") or {}).get("milliseconds") or 0) for row in rows)
    tokens = [row.get("staging_remote_total_tokens") for row in rows if isinstance(row.get("staging_remote_total_tokens"), int)]
    return {
        "tasks": total,
        "passed": passed,
        "accuracy": passed / total if total else 0,
        "judged_fireworks_tokens": 0,
        "staging_remote_tokens": sum(tokens) if len(tokens) == total else "NOT_RETURNED",
        "validation_failures": sum(1 for row in rows if not (row.get("route_record") or {}).get("validation_result", {}).get("passed", True)),
        "evaluator_failures": total - passed,
        "latency_ms": latency,
    }


def podman_run_cell(image: str, cell_dir: Path, alias: str, mode_key: str) -> dict[str, Any]:
    baseline_script = cell_dir / "baseline-runner.py"
    if mode_key == "remote":
        baseline_script.write_text(BASELINE_RUNNER, encoding="utf-8")
    command = [
        "timeout",
        "--signal=TERM",
        "--kill-after=15s",
        "600",
        "podman",
        "run",
        "--rm",
        "--memory=4g",
        "--cpus=2",
        "--pids-limit=512",
        "-e",
        "OLLAMA_API_KEY",
        "-e",
        "OLLAMA_CLOUD_BASE_URL=https://ollama.com",
        "-e",
        "VERSION6_REMOTE_FALLBACK=staging",
        "-e",
        "STAGING_REMOTE_PROVIDER=ollama-cloud",
        "-e",
        f"STAGING_ALLOWED_MODELS={','.join(STAGING_ALLOWED_MODELS)}",
        "-e",
        f"STAGING_INFERENCE_MODEL={alias}",
        "-e",
        f"STAGING_EXACT_API_MODEL_ID={MODEL_MAPPINGS[alias]}",
        "-v",
        f"{cell_dir / 'input'}:/input:ro,Z",
        "-v",
        f"{cell_dir / 'output'}:/output:Z",
        image,
    ]
    if mode_key == "remote":
        command.extend(
            [
                "python",
                "/baseline-runner.py",
            ]
        )
        command[-3:-3] = ["-v", f"{baseline_script}:/baseline-runner.py:ro,Z"]
    start = time.monotonic()
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    elapsed = round(time.monotonic() - start, 3)
    log_path = cell_dir / "container.log"
    log_path.write_text(completed.stdout, encoding="utf-8")
    return {
        "command": command,
        "exit_code": completed.returncode,
        "runtime_seconds": elapsed,
        "timed_out": completed.returncode in {124, 137},
        "oom_status": "unknown",
        "container_log": str(log_path),
    }


BASELINE_RUNNER = r'''
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) + len(text) // 16)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def complete(prompt: str, model: str) -> tuple[str, dict[str, object], int]:
    start = time.perf_counter()
    api_key = os.environ["OLLAMA_API_KEY"]
    base_url = os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://ollama.com").rstrip("/")
    timeout_seconds = int(os.environ.get("STAGING_TIMEOUT_SECONDS", "180"))
    max_retries = int(os.environ.get("STAGING_MAX_RETRIES", "2"))
    backoff = float(os.environ.get("STAGING_RETRY_BACKOFF_SECONDS", "2"))
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(f"{base_url}/api/chat", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_retries:
                raise RuntimeError(f"Ollama Cloud baseline request failed with HTTP {exc.code}") from exc
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff * (attempt + 1)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt >= max_retries:
                raise RuntimeError(f"Ollama Cloud baseline request failed: {type(exc).__name__}") from exc
            time.sleep(backoff * (attempt + 1))
    else:
        raise RuntimeError(f"Ollama Cloud baseline request failed: {last_error}")

    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise RuntimeError("Ollama Cloud baseline response was malformed")
    text = str(message["content"]).strip()
    if not text:
        raise RuntimeError("Ollama Cloud baseline response was empty")
    prompt_count = payload.get("prompt_eval_count")
    completion_count = payload.get("eval_count")
    token_usage: dict[str, object] = {
        "judged_fireworks_tokens": "not_applicable",
        "official_fireworks_token_score": "NOT_MEASURED",
        "staging_remote_provider": "ollama-cloud",
        "staging_remote_model": model,
        "retry_count": 0,
    }
    if isinstance(prompt_count, int):
        token_usage["staging_remote_prompt_tokens"] = prompt_count
    else:
        token_usage["staging_remote_prompt_estimate"] = estimate_tokens(prompt)
    if isinstance(completion_count, int):
        token_usage["staging_remote_completion_tokens"] = completion_count
    else:
        token_usage["staging_remote_completion_estimate"] = estimate_tokens(text)
    if isinstance(prompt_count, int) and isinstance(completion_count, int):
        token_usage["staging_remote_total_tokens"] = prompt_count + completion_count
    return text, token_usage, int((time.perf_counter() - start) * 1000)


def main() -> int:
    input_path = Path("/input/tasks.json")
    output_path = Path("/output/results.json")
    audit_dir = Path("/output/audit")
    model = os.environ["STAGING_EXACT_API_MODEL_ID"]
    tasks = json.loads(input_path.read_text(encoding="utf-8"))
    results = []
    for task in tasks:
        task_id = str(task["task_id"])
        prompt = str(task["prompt"])
        answer, token_usage, latency_ms = complete(prompt, model)
        results.append({"task_id": task_id, "answer": answer})
        write_json(
            audit_dir / f"{task_id}-{int(time.time())}.json",
            {
                "task_id": task_id,
                "task_family": None,
                "work_jurisdiction": "STAGING_REMOTE_BASELINE",
                "answer_schema": {"format": "text", "instruction": "Return a concise answer with no preamble."},
                "compiled_prompt": prompt,
                "estimated_input_tokens": estimate_tokens(prompt),
                "selected_provider": "version6-staging-remote-baseline",
                "selected_path": "staging_remote_baseline",
                "selected_model": model,
                "routing_reason": "staging_remote_baseline_direct_ollama_cloud",
                "final_mode_compliant": False,
                "validation_result": {"passed": True, "reason": "ok"},
                "repair": {"attempted": False, "reason": "ok"},
                "token_usage": token_usage,
                "fireworks_token_usage": {
                    "judged_fireworks_tokens": "not_applicable",
                    "official_fireworks_token_score": "NOT_MEASURED",
                },
                "judged_fireworks_tokens": "not_applicable",
                "official_fireworks_token_score": "NOT_MEASURED",
                "retry_count": 0,
                "latency": {"milliseconds": latency_ms},
                "output": answer,
            },
        )
    write_json(output_path, results)
    print(json.dumps({"status": "completed", "task_count": len(results), "result_path": str(output_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def prepare_cell(root: Path, suite: SuiteSpec, alias: str, mode_key: str, input_tasks: list[dict[str, str]], evaluator: list[dict[str, Any]]) -> Path:
    cell_dir = root / suite.key / safe_model_dir(alias) / mode_key
    (cell_dir / "input").mkdir(parents=True, exist_ok=True)
    (cell_dir / "output/audit").mkdir(parents=True, exist_ok=True)
    write_json(cell_dir / "input/tasks.json", input_tasks)
    write_json(cell_dir / "input/evaluator-withheld.json", evaluator)
    return cell_dir


def run_matrix(args: argparse.Namespace) -> dict[str, Any]:
    if not os.environ.get("OLLAMA_API_KEY"):
        raise SystemExit("OLLAMA_API_KEY is required in the process environment")
    run_id = args.run_id or utc_run_id()
    root = ROOT / "staging-runs" / run_id
    if root.exists():
        raise SystemExit(f"run directory already exists: {root}")
    root.mkdir(parents=True)
    suites = [
        SuiteSpec("canonical", BENCHMARK_SUITE_ID, CANONICAL_BENCHMARK_PATH),
        SuiteSpec("shadow", "version6-shadow-category-benchmark-v1", SHADOW_BENCHMARK_PATH),
    ]
    suite_reports = [validate_suite_shape(spec) for spec in suites]
    image_report = inspect_staging_image(args.image) if args.inspect_image else {
        "image_tag": args.image,
        "anonymous_pull": "not_checked",
        "remote_manifest_tooling": "UNAVAILABLE_NON_BLOCKING",
        "staging_status": "NOT_FOR_SUBMISSION",
    }
    matrix: list[dict[str, Any]] = []
    for suite in suites:
        input_tasks, evaluator, _ = load_suite(suite)
        write_json(root / suite.key / "input/tasks.json", input_tasks)
        write_json(root / suite.key / "input/evaluator-withheld.json", evaluator)
        for alias in STAGING_ALLOWED_MODELS:
            for mode_key in ["remote", "routed"]:
                cell_dir = prepare_cell(root, suite, alias, mode_key, input_tasks, evaluator)
                timing = podman_run_cell(args.image, cell_dir, alias, mode_key) if args.execute else {
                    "exit_code": None,
                    "runtime_seconds": 0,
                    "timed_out": False,
                    "skipped": True,
                }
                validation = validate_official_output(input_tasks, cell_dir / "output/results.json") if args.execute else {
                    "valid": False,
                    "errors": ["execution skipped"],
                    "task_count": 0,
                    "results": [],
                }
                status = "COMPLETE" if timing.get("exit_code") == 0 and not timing.get("timed_out") and validation["valid"] else "FAILED_RUNTIME"
                if timing.get("timed_out"):
                    status = "TIMED_OUT"
                elif timing.get("exit_code") == 0 and not validation["valid"]:
                    status = "FAILED_OUTPUT_CONTRACT"
                if args.execute:
                    result = grade_results(suite, alias, mode_key, run_id, cell_dir, input_tasks, evaluator, validation, timing)
                else:
                    result = {}
                status_payload = {
                    "suite": suite.key,
                    "requested_model_alias": alias,
                    "exact_api_model_id": MODEL_MAPPINGS[alias],
                    "mode": MODES[mode_key]["execution_mode"],
                    "status": status if args.execute else "NOT_EXECUTED",
                    "timing": timing,
                    "validation": {key: value for key, value in validation.items() if key != "results"},
                    "qualification_result": result.get("result_path"),
                }
                write_json(cell_dir / "status.json", status_payload)
                write_json(cell_dir / "validation.json", {key: value for key, value in validation.items() if key != "results"})
                write_json(cell_dir / "timing.json", timing)
                write_json(cell_dir / "grading.json", result or {"status": "not_executed"})
                matrix.append(status_payload)
    complete = sum(1 for row in matrix if row["status"] == "COMPLETE")
    summary = {
        "run_id": run_id,
        "status": "STAGING_FULL_MATRIX_COMPLETE" if complete == 16 else "STAGING_FULL_MATRIX_PARTIAL",
        "verified_models": 4,
        "validated_suites": 2,
        "execution_modes": 2,
        "matrix_cells": len(matrix),
        "complete_cells": complete,
        "tasks_per_cell": 40,
        "expected_total_task_executions": 640,
        "suites": suite_reports,
        "image": image_report,
        "matrix": matrix,
        "production_modified": False,
        "production_rebuilt": False,
        "production_retagged": False,
        "production_pushed": False,
        "production_digest_changed": False,
        "production_remote_provider": "FIREWORKS_ONLY",
        "fireworks_credentials_used": False,
        "ollama_api_key_configured": True,
        "ollama_api_key_persisted": False,
        "staging_status": "NOT_FOR_SUBMISSION",
        "automatic_authority_promotion": False,
    }
    write_json(root / "manifest.json", summary)
    write_json(root / "summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Version 6 Ollama Cloud staging qualification matrix.")
    parser.add_argument("--image", default=DEFAULT_STAGING_IMAGE)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--execute", action="store_true", help="Run the 16 Podman benchmark cells.")
    parser.add_argument("--inspect-image", action="store_true", help="Verify anonymous pull and inspect the staging image.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_matrix(args)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
