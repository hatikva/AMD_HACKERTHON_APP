from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .pipeline import (
    OLLAMA_CLOUD_MODEL_MAPPINGS,
    ROOT,
    STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
    VERSION_5_LOCAL_MODEL,
    VERSION_5_LOCAL_PROVIDER,
    VERSION_6_STAGING_PROVIDER,
    VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
    parse_allowed_models,
    parse_staging_allowed_models,
    resolve_ollama_cloud_model,
    run_tasks_file,
    write_json,
)


BENCHMARK_SUITE_ID = "version5-category-benchmark-v2"
BENCHMARK_SCHEMA = "amd_hackathon.local_category_benchmarks.v2"
CANONICAL_BENCHMARK_PATH = ROOT / "benchmarks/categories/version5_local_category_benchmarks_v2.json"
CANONICAL_CATEGORIES = [
    "FACTUAL_KNOWLEDGE",
    "MATHEMATICAL_REASONING",
    "SENTIMENT_CLASSIFICATION",
    "TEXT_SUMMARISATION",
    "NAMED_ENTITY_RECOGNITION",
    "CODE_DEBUGGING",
    "LOGICAL_DEDUCTIVE_REASONING",
    "CODE_GENERATION",
]
CODE_EVALUATORS = {
    "python_unit_tests",
    "python_unit_tests_with_exceptions",
    "python_behavioral_tests",
}


@dataclass(frozen=True)
class BenchmarkSuite:
    path: Path
    suite_id: str
    content_hash: str
    payload: dict[str, Any]

    @property
    def tasks(self) -> list[dict[str, Any]]:
        return list(self.payload["tasks"])


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_category_benchmark(path: Path = CANONICAL_BENCHMARK_PATH) -> BenchmarkSuite:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_category_benchmark(payload)
    return BenchmarkSuite(path=path, suite_id=BENCHMARK_SUITE_ID, content_hash=file_sha256(path), payload=payload)


def validate_category_benchmark(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("schema") != BENCHMARK_SCHEMA:
        errors.append(f"schema must be {BENCHMARK_SCHEMA}")
    categories = payload.get("categories")
    tasks = payload.get("tasks")
    if not isinstance(categories, list):
        errors.append("categories must be a list")
        categories = []
    if not isinstance(tasks, list):
        errors.append("tasks must be a list")
        tasks = []

    category_ids = [row.get("id") for row in categories if isinstance(row, dict)]
    if set(category_ids) != set(CANONICAL_CATEGORIES):
        errors.append(f"categories must match canonical set: {CANONICAL_CATEGORIES}")
    if len(categories) != 8:
        errors.append(f"category count must be 8, got {len(categories)}")
    if len(tasks) != 40:
        errors.append(f"task count must be 40, got {len(tasks)}")

    task_ids: list[str] = []
    prompts: list[str] = []
    by_category: dict[str, list[dict[str, Any]]] = {category: [] for category in CANONICAL_CATEGORIES}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"task at index {index} must be an object")
            continue
        task_id = str(task.get("id", ""))
        prompt = str(task.get("prompt", ""))
        category = str(task.get("task_category", ""))
        task_ids.append(task_id)
        prompts.append(prompt)
        if category not in by_category:
            errors.append(f"task {task_id} has non-canonical task_category {category}")
        else:
            by_category[category].append(task)
        if task.get("difficulty_hint") not in [1, 2, 3, 4, 5]:
            errors.append(f"task {task_id} has invalid difficulty_hint {task.get('difficulty_hint')}")
        if not isinstance(task.get("evaluation"), dict):
            errors.append(f"task {task_id} must include evaluation metadata")
        if "evaluation" in model_visible_task(task):
            errors.append(f"task {task_id} exposes evaluation in model-visible projection")
        forbidden_visible = {"task_category", "task_family", "difficulty_hint", "expected_format", "evidence_refs"}
        leaked = sorted(forbidden_visible.intersection(model_visible_task(task)))
        if leaked:
            errors.append(f"task {task_id} exposes benchmark metadata in model-visible projection: {leaked}")

    if len(task_ids) != len(set(task_ids)):
        errors.append("task IDs must be unique")
    if len(prompts) != len(set(prompts)):
        errors.append("prompts must be unique")
    for category, rows in by_category.items():
        if len(rows) != 5:
            errors.append(f"{category} must contain 5 tasks, got {len(rows)}")
        difficulties = sorted(row.get("difficulty_hint") for row in rows)
        if difficulties != [1, 2, 3, 4, 5]:
            errors.append(f"{category} must contain difficulty levels [1, 2, 3, 4, 5], got {difficulties}")

    if errors:
        raise ValueError("; ".join(errors))


def model_visible_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": str(task["id"]),
        "prompt": str(task["prompt"]),
    }


def evaluator_record(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["id"],
        "task_category": task["task_category"],
        "task_family": task.get("task_family"),
        "difficulty_hint": task["difficulty_hint"],
        "expected_format": task.get("expected_format"),
        "evaluation": task["evaluation"],
    }


def index_submission_results(results: list[dict[str, Any]], expected_ids: set[str]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, row in enumerate(results):
        if not isinstance(row, dict):
            errors.append(f"result at index {index} must be an object")
            continue
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"result at index {index} is missing task_id")
            continue
        if task_id in indexed:
            errors.append(f"duplicate result task_id: {task_id}")
        if task_id not in expected_ids:
            errors.append(f"unknown result task_id: {task_id}")
        if "answer" not in row:
            errors.append(f"result {task_id} is missing answer")
        indexed[task_id] = row
    missing = sorted(expected_ids.difference(indexed))
    if missing:
        errors.append(f"missing results for task_id: {', '.join(missing)}")
    if errors:
        raise ValueError("; ".join(errors))
    return indexed


def normalize_text(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9.+#/-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_json_output(output: str) -> Any:
    return json.loads(output)


def evaluate_output(output: str, evaluation: dict[str, Any]) -> dict[str, Any]:
    evaluator_type = evaluation.get("type")
    if evaluator_type == "normalized_exact_match":
        accepted = [evaluation.get("expected"), *evaluation.get("accepted_answers", [])]
        passed = normalize_text(output) in {normalize_text(item) for item in accepted}
        return {"implemented": True, "passed": passed, "type": evaluator_type}
    if evaluator_type == "numeric_exact_match":
        try:
            actual = float(normalize_text(output))
            expected = float(evaluation["expected"])
        except (TypeError, ValueError):
            return {"implemented": True, "passed": False, "type": evaluator_type, "reason": "not_numeric"}
        return {"implemented": True, "passed": actual == expected, "type": evaluator_type}
    if evaluator_type == "label_exact_match":
        label = normalize_text(output)
        labels = {normalize_text(item) for item in evaluation.get("labels", [])}
        expected = normalize_text(evaluation.get("expected"))
        return {"implemented": True, "passed": label == expected and label in labels, "type": evaluator_type}
    if evaluator_type == "unordered_set_match":
        try:
            actual = parse_json_output(output)
        except json.JSONDecodeError:
            actual = [part.strip() for part in output.split(",") if part.strip()]
        expected = evaluation.get("expected", [])
        return {
            "implemented": True,
            "passed": {normalize_text(item) for item in actual} == {normalize_text(item) for item in expected},
            "type": evaluator_type,
        }
    if evaluator_type == "ordered_list_match":
        try:
            actual = parse_json_output(output)
        except json.JSONDecodeError:
            actual = [part.strip() for part in output.split(",") if part.strip()]
        expected = evaluation.get("expected", [])
        return {
            "implemented": True,
            "passed": [normalize_text(item) for item in actual] == [normalize_text(item) for item in expected],
            "type": evaluator_type,
        }
    if evaluator_type == "json_deep_exact_match":
        try:
            actual = parse_json_output(output)
        except json.JSONDecodeError:
            return {"implemented": True, "passed": False, "type": evaluator_type, "reason": "invalid_json"}
        return {"implemented": True, "passed": actual == evaluation.get("expected"), "type": evaluator_type}
    if evaluator_type == "summary_rubric":
        normalized_output = normalize_text(output)
        required = [normalize_text(item) for item in evaluation.get("required_facts", [])]
        max_words = int(evaluation.get("max_words", 10**9))
        passed = all(fact in normalized_output for fact in required) and len(output.split()) <= max_words
        return {
            "implemented": True,
            "passed": passed,
            "type": evaluator_type,
            "required_facts_found": sum(1 for fact in required if fact in normalized_output),
            "required_facts_total": len(required),
            "word_count": len(output.split()),
            "max_words": max_words,
        }
    if evaluator_type in CODE_EVALUATORS:
        syntax = python_syntax_status(output, evaluation.get("entrypoint"))
        return {
            "implemented": False,
            "passed": False,
            "type": evaluator_type,
            "status": "blocked",
            "reason": "code_execution_evaluator_requires_isolated_sandbox",
            **syntax,
            "test_pass_count": 0,
            "test_failure_count": len(evaluation.get("tests", [])),
            "timeout": False,
            "runtime_error": None,
        }
    raise ValueError(f"unsupported evaluator type: {evaluator_type}")


def python_syntax_status(source: str, entrypoint: str | None) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"syntax_valid": False, "function_exists": False, "syntax_error": str(exc)}
    function_exists = any(isinstance(node, ast.FunctionDef) and node.name == entrypoint for node in tree.body)
    return {"syntax_valid": True, "function_exists": function_exists, "syntax_error": None}


def candidate_metadata(provider: str, model: str | None) -> dict[str, Any]:
    if provider == "fireworks":
        allowed = parse_allowed_models()
        exact_model = model or (allowed[0] if allowed else None)
        if not exact_model:
            raise RuntimeError("Fireworks benchmark requires --model or ALLOWED_MODELS")
        if allowed and exact_model not in allowed:
            raise RuntimeError(f"Fireworks model {exact_model} is not present in ALLOWED_MODELS")
        return {"provider": "fireworks", "model": exact_model, "allowed_models_source": "ALLOWED_MODELS"}
    if provider == "llama-cpp":
        return {
            "provider": "llama-cpp",
            "model": model or os.environ.get("LLAMA_MODEL_PATH", VERSION_5_LOCAL_MODEL["image_path"]),
            "model_name": os.environ.get("LLAMA_MODEL_NAME", VERSION_5_LOCAL_MODEL["model_name"]),
            "model_sha256": VERSION_5_LOCAL_MODEL["sha256"],
            "runtime": os.environ.get("LLAMA_CPP_BINARY", "/app/bin/llama-cli"),
        }
    if provider == "version5":
        return {
            "provider": "version5",
            "model": model or os.environ.get("OLLAMA_MODEL_NAME", VERSION_5_LOCAL_MODEL["model_name"]),
            "model_sha256": VERSION_5_LOCAL_MODEL["sha256"],
            "policy_version": "version_5_local_certification_lookup",
            "local_runtime_provider": VERSION_5_LOCAL_PROVIDER,
            "runtime_certification": "OLLAMA_CERTIFIED",
        }
    if provider == VERSION_5_LOCAL_PROVIDER:
        return {
            "provider": VERSION_5_LOCAL_PROVIDER,
            "model": model or os.environ.get("OLLAMA_MODEL_NAME", VERSION_5_LOCAL_MODEL["model_name"]),
            "model_sha256": VERSION_5_LOCAL_MODEL["sha256"],
            "base_url": os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            "final_mode_compliant": True,
            "runtime_certification": "OLLAMA_CERTIFIED",
            "jurisdiction_authorization": "benchmark_evidence_only_not_registry_promotion",
        }
    if provider == "ollama-demo":
        return {
            "provider": "ollama-demo",
            "model": model or os.environ.get("MODEL_NAME", "qwen2.5-coder:3b"),
            "base_url": os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            "final_mode_compliant": False,
        }
    if provider in {VERSION_6_STAGING_PROVIDER, VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER}:
        supplied_model = model or os.environ.get("STAGING_INFERENCE_MODEL", "")
        allowed = parse_staging_allowed_models()
        api_model = resolve_ollama_cloud_model(supplied_model, allowed)
        return {
            "provider": provider,
            "remote_provider": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
            "supplied_model": supplied_model,
            "requested_model_alias": supplied_model,
            "exact_api_model_id": api_model,
            "model": api_model,
            "mapping": OLLAMA_CLOUD_MODEL_MAPPINGS[supplied_model],
            "allowed_models_source": "STAGING_ALLOWED_MODELS",
            "official_fireworks_token_score": "NOT_MEASURED",
            "evidence_class": "staging_only",
            "submission_eligible": False,
            "automatic_authority_promotion": False,
            "not_for_submission": True,
            "production_authorization_registry_mutated": False,
        }
    if provider == "mock":
        return {"provider": "mock", "model": model or "mock-model"}
    raise ValueError(f"unsupported benchmark provider: {provider}")


def benchmark_provider_override(provider: str) -> str:
    return provider


def run_category_benchmark(
    suite_path: Path = CANONICAL_BENCHMARK_PATH,
    provider: str = "mock",
    model: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    suite = load_category_benchmark(suite_path)
    candidate = candidate_metadata(provider, model)
    run_id = f"{BENCHMARK_SUITE_ID}-{provider}-{int(time.time())}"
    destination = output_path or ROOT / "qualification/results" / f"{run_id}.json"
    run_dir = destination.parent / f"{run_id}-run"
    input_dir = run_dir / "input"
    output_dir = run_dir / "output"
    task_run_dir = run_dir / "audit"
    input_path = input_dir / "tasks.json"
    output_results_path = output_dir / "results.json"
    records: list[dict[str, Any]] = []
    provider_override = benchmark_provider_override(provider)
    visible_tasks = [model_visible_task(task) for task in suite.tasks]
    evaluator_by_id = {task["id"]: evaluator_record(task) for task in suite.tasks}
    write_json(input_path, visible_tasks)

    previous_run_dir = os.environ.get("APP_RUN_DIR")
    previous_model_name = os.environ.get("MODEL_NAME")
    previous_ollama_model_name = os.environ.get("OLLAMA_MODEL_NAME")
    os.environ["APP_RUN_DIR"] = str(task_run_dir)
    if provider == "ollama-demo" and model:
        os.environ["MODEL_NAME"] = model
    previous_staging_model = os.environ.get("STAGING_INFERENCE_MODEL")
    if provider == VERSION_5_LOCAL_PROVIDER and model:
        os.environ["OLLAMA_MODEL_NAME"] = model
    if provider == VERSION_6_STAGING_PROVIDER and model:
        os.environ["STAGING_INFERENCE_MODEL"] = model
    try:
        run_payload = run_tasks_file(input_path=input_path, output_path=output_results_path, provider_override=provider_override)
    finally:
        if previous_run_dir is None:
            os.environ.pop("APP_RUN_DIR", None)
        else:
            os.environ["APP_RUN_DIR"] = previous_run_dir
        if previous_model_name is None:
            os.environ.pop("MODEL_NAME", None)
        else:
            os.environ["MODEL_NAME"] = previous_model_name
        if previous_ollama_model_name is None:
            os.environ.pop("OLLAMA_MODEL_NAME", None)
        else:
            os.environ["OLLAMA_MODEL_NAME"] = previous_ollama_model_name
        if previous_staging_model is None:
            os.environ.pop("STAGING_INFERENCE_MODEL", None)
        else:
            os.environ["STAGING_INFERENCE_MODEL"] = previous_staging_model

    submission_results = index_submission_results(
        run_payload["results"],
        expected_ids=set(evaluator_by_id),
    )
    audit_by_id = {record["task_id"]: record for record in run_payload["audit_records"]}

    for benchmark_task in suite.tasks:
        task_id = benchmark_task["id"]
        visible = model_visible_task(benchmark_task)
        route_record = audit_by_id[task_id]
        evaluation = evaluator_by_id[task_id]
        answer = str(submission_results[task_id]["answer"])
        try:
            evaluation_result = evaluate_output(answer, evaluation["evaluation"])
        except ValueError as exc:
            evaluation_result = {
                "implemented": False,
                "passed": False,
                "type": evaluation["evaluation"].get("type"),
                "status": "unsupported",
                "reason": str(exc),
            }
        records.append(
            {
                "task_id": task_id,
                "task_category": evaluation["task_category"],
                "task_family": evaluation.get("task_family"),
                "difficulty_hint": evaluation["difficulty_hint"],
                "model_visible_task": visible,
                "evaluator": {
                    "type": evaluation["evaluation"].get("type"),
                    "withheld_from_model": True,
                },
                "evaluation_result": evaluation_result,
                "route_record": route_record,
                "judged_fireworks_tokens": route_record["judged_fireworks_tokens"],
                "official_fireworks_token_score": route_record["official_fireworks_token_score"],
                "staging_remote_prompt_tokens": route_record["token_usage"].get("staging_remote_prompt_tokens"),
                "staging_remote_completion_tokens": route_record["token_usage"].get("staging_remote_completion_tokens"),
                "staging_remote_total_tokens": route_record["token_usage"].get("staging_remote_total_tokens"),
                "local_estimated_input_tokens": route_record["token_usage"].get("local_prompt_estimate", 0),
                "local_estimated_output_tokens": route_record["token_usage"].get("local_completion_estimate", 0),
            }
        )

    payload = {
        "schema": "amd_hackathon.qualification_results.v1",
        "benchmark_suite": suite.suite_id,
        "benchmark_hash": suite.content_hash,
        "benchmark_path": str(suite.path),
        "run_id": run_id,
        "candidate": candidate,
        "model_visible_tasks_path": str(input_path),
        "official_results_path": str(output_results_path),
        "production_path_used": True,
        "qualification_status": "PENDING_POLICY_REVIEW",
        "authorization_registry_mutated": False,
        "policy_thresholds": "blocked_until_final_thresholds_are_defined",
        "summary": summarize_results(records),
        "results": records,
    }
    write_json(destination, payload)
    payload["result_path"] = str(destination)
    return payload


def summarize_results(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    passed = sum(1 for row in records if row["evaluation_result"].get("passed"))
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_category[row["task_category"]].append(row)
        by_difficulty[str(row["difficulty_hint"])].append(row)
    return {
        "overall_tasks": total,
        "overall_passed": passed,
        "overall_accuracy": passed / total if total else 0,
        "by_category": {category: summarize_group(rows) for category, rows in sorted(by_category.items())},
        "by_difficulty": {difficulty: summarize_group(rows) for difficulty, rows in sorted(by_difficulty.items())},
        "validation_failures": sum(1 for row in records if not row["route_record"]["validation_result"]["passed"]),
        "evaluator_failures": sum(1 for row in records if not row["evaluation_result"].get("passed")),
        "runtime_failures": sum(1 for row in records if row["route_record"].get("fallback_reason")),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if row["evaluation_result"].get("passed"))
    numeric_fireworks_tokens = [row["judged_fireworks_tokens"] for row in rows if isinstance(row["judged_fireworks_tokens"], int)]
    fireworks_tokens: int | str = (
        sum(numeric_fireworks_tokens) if len(numeric_fireworks_tokens) == len(rows) else "NOT_MEASURED"
    )
    latency = sum(row["route_record"]["latency"]["milliseconds"] for row in rows)
    return {
        "tasks": total,
        "passed": passed,
        "accuracy": passed / total if total else 0,
        "judged_fireworks_tokens": fireworks_tokens,
        "latency_ms": latency,
        "validation_failures": sum(1 for row in rows if not row["route_record"]["validation_result"]["passed"]),
        "evaluator_failures": sum(1 for row in rows if not row["evaluation_result"].get("passed")),
    }
