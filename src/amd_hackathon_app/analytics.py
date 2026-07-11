from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .benchmarks import (
    BENCHMARK_SUITE_ID,
    CANONICAL_BENCHMARK_PATH,
    CANONICAL_CATEGORIES,
    file_sha256,
    load_category_benchmark,
    model_visible_task,
)
from .pipeline import ROOT, VERSION_5_LOCAL_PROVIDER, normalize_task_family


ANALYTICS_SCHEMA = "amd_hackathon.version5_authority_analytics.v1"
VERSION6_ANALYTICS_SCHEMA = "amd_hackathon.version6_submission_analytics.v1"
CATEGORY_TASK_TOTAL = 5
QUALIFICATION_ONLY_PROVIDERS = {"ollama-demo", "llama-cpp"}

FAMILY_TO_CATEGORY = {
    "factual_qa": "FACTUAL_KNOWLEDGE",
    "math_reasoning": "MATHEMATICAL_REASONING",
    "sentiment": "SENTIMENT_CLASSIFICATION",
    "summarization": "TEXT_SUMMARISATION",
    "named_entity_recognition": "NAMED_ENTITY_RECOGNITION",
    "code_debugging": "CODE_DEBUGGING",
    "logic_puzzles": "LOGICAL_DEDUCTIVE_REASONING",
    "code_generation": "CODE_GENERATION",
}

CATEGORY_TO_SCOPE = {
    "FACTUAL_KNOWLEDGE": "SHORT_FACTUAL_ANSWERING",
    "MATHEMATICAL_REASONING": "MATH_LIGHT",
    "SENTIMENT_CLASSIFICATION": "SENTIMENT_CLASSIFICATION",
    "TEXT_SUMMARISATION": "SIMPLE_SUMMARIZATION",
    "NAMED_ENTITY_RECOGNITION": "NAMED_ENTITY_RECOGNITION",
    "CODE_DEBUGGING": "CODE_DEBUGGING_SMALL",
    "LOGICAL_DEDUCTIVE_REASONING": "LOGICAL_DEDUCTION_LIGHT",
    "CODE_GENERATION": "CODE_GENERATION_SMALL",
}

WORK_SCOPES = [
    "TASK_FAMILY_CLASSIFICATION",
    "SHORT_FACTUAL_ANSWERING",
    "MATH_LIGHT",
    "SENTIMENT_CLASSIFICATION",
    "SIMPLE_SUMMARIZATION",
    "NAMED_ENTITY_RECOGNITION",
    "CODE_DEBUGGING_SMALL",
    "LOGICAL_DEDUCTION_LIGHT",
    "CODE_GENERATION_SMALL",
    "ANSWER_SCHEMA_SELECTION",
    "DETERMINISTIC_VALIDATION",
    "STRUCTURAL_REPAIR",
    "FIREWORKS_FALLBACK",
    "TOKEN_BUDGETING",
]


def load_result_files(results_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    payloads: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(results_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") == "amd_hackathon.qualification_results.v1":
            payloads.append((path, payload))
    return payloads


def result_identity(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload.get("candidate") or {}
    provider = str(candidate.get("provider") or "unknown")
    model = str(candidate.get("model") or "unknown")
    selected_pairs = sorted(
        {
            (
                str((row.get("route_record") or {}).get("selected_provider") or ""),
                str((row.get("route_record") or {}).get("selected_model") or ""),
            )
            for row in payload.get("results", [])
            if row.get("route_record")
        }
    )
    effective_provider = selected_pairs[0][0] if len(selected_pairs) == 1 and selected_pairs[0][0] else provider
    effective_model = selected_pairs[0][1] if len(selected_pairs) == 1 and selected_pairs[0][1] else model
    if provider == "version5" and effective_provider == "fireworks":
        display_name = f"version5 fallback -> {effective_model}"
        evidence_class = "final_policy_fallback_evidence"
        final_provider_evidence = True
        qualification_only = False
    elif provider in QUALIFICATION_ONLY_PROVIDERS:
        display_name = f"{provider} / {model}"
        evidence_class = "qualification_only_evidence"
        final_provider_evidence = False
        qualification_only = True
    elif provider == VERSION_5_LOCAL_PROVIDER:
        display_name = f"{provider} / {model}"
        evidence_class = "final_provider_evidence"
        final_provider_evidence = True
        qualification_only = False
    else:
        display_name = f"{provider} / {model}"
        evidence_class = "final_provider_evidence"
        final_provider_evidence = True
        qualification_only = False
    return {
        "id": f"{provider}|{model}|{path.name}",
        "display_name": display_name,
        "provider": provider,
        "model": model,
        "effective_provider": effective_provider,
        "effective_model": effective_model,
        "result_file": str(path),
        "result_file_name": path.name,
        "evidence_class": evidence_class,
        "final_provider_evidence": final_provider_evidence,
        "qualification_only": qualification_only,
    }


def safe_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    records = payload.get("results", [])
    total = len(records)
    passed = sum(1 for row in records if (row.get("evaluation_result") or {}).get("passed") is True)
    return {
        "overall_tasks": total,
        "overall_passed": passed,
        "overall_accuracy": passed / total if total else 0,
        "judged_fireworks_tokens": sum(int(row.get("judged_fireworks_tokens") or 0) for row in records),
        "runtime_failures": 0,
        "validation_failures": 0,
        "evaluator_failures": total - passed,
        "by_category": {},
    }


def overall_metrics(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = safe_summary(payload)
    records = payload.get("results", [])
    latency = sum(int(((row.get("route_record") or {}).get("latency") or {}).get("milliseconds") or 0) for row in records)
    fireworks_tokens = sum(int(row.get("judged_fireworks_tokens") or 0) for row in records)
    return {
        **result_identity(path, payload),
        "benchmark_suite": payload.get("benchmark_suite"),
        "benchmark_hash": payload.get("benchmark_hash"),
        "overall_tasks": int(summary.get("overall_tasks") or 0),
        "overall_passed": int(summary.get("overall_passed") or 0),
        "overall_accuracy": float(summary.get("overall_accuracy") or 0),
        "judged_fireworks_tokens": fireworks_tokens,
        "runtime_failures": int(summary.get("runtime_failures") or 0),
        "validation_failures": int(summary.get("validation_failures") or 0),
        "evaluator_failures": int(summary.get("evaluator_failures") or 0),
        "latency_ms": latency,
        "qualification_status": payload.get("qualification_status", "PENDING_POLICY_REVIEW"),
        "promotion_status": "reviewed_evidence_only_not_runtime_authorization",
    }


def per_category_metrics(path: Path, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    identity = result_identity(path, payload)
    by_category = safe_summary(payload).get("by_category") or {}
    metrics: dict[str, dict[str, Any]] = {}
    for category in CANONICAL_CATEGORIES:
        row = by_category.get(category) or {}
        tasks = int(row.get("tasks") or 0)
        passed = int(row.get("passed") or 0)
        metrics[category] = {
            **identity,
            "category": category,
            "tasks": tasks,
            "passed": passed,
            "accuracy": float(row.get("accuracy") or (passed / tasks if tasks else 0)),
            "judged_fireworks_tokens": int(row.get("judged_fireworks_tokens") or 0),
            "validation_failures": int(row.get("validation_failures") or 0),
            "evaluator_failures": int(row.get("evaluator_failures") or max(0, tasks - passed)),
            "latency_ms": int(row.get("latency_ms") or 0),
        }
    return metrics


def ranking_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        -int(row["passed"]),
        int(row["judged_fireworks_tokens"]),
        int(row["validation_failures"]),
        int(row["latency_ms"]),
        str(row["id"]),
    )


def explain_recommendation(category: str, winner: dict[str, Any], runner_up: dict[str, Any] | None, rows: list[dict[str, Any]]) -> str:
    if all(int(row["passed"]) == 0 for row in rows):
        return f"Current evidence says all candidates are poor for {category}; keep fallback or retest before assigning authority."
    if runner_up and int(winner["passed"]) == int(runner_up["passed"]):
        if int(winner["judged_fireworks_tokens"]) < int(runner_up["judged_fireworks_tokens"]):
            return "Winner ties on passed count and wins the Fireworks-token tie-break."
        if int(winner["validation_failures"]) < int(runner_up["validation_failures"]):
            return "Winner ties on passed count and tokens, then wins by fewer validation failures."
        if int(winner["latency_ms"]) < int(runner_up["latency_ms"]):
            return "Winner ties on passed count, tokens, and validation failures, then wins by lower latency."
    if winner["qualification_only"]:
        return "Best score is qualification-only evidence and is blocked from authority promotion until rerun through a final provider identity."
    return "Winner has the strongest current passed-count evidence under the required tie-break order."


def confidence_for(winner: dict[str, Any], runner_up: dict[str, Any] | None) -> str:
    passed = int(winner["passed"])
    if passed == CATEGORY_TASK_TOTAL and not winner["qualification_only"] and int(winner["validation_failures"]) == 0:
        return "high"
    if passed >= 3 and (runner_up is None or passed > int(runner_up["passed"])):
        return "medium"
    return "low"


def promotion_status_for(winner: dict[str, Any]) -> str:
    if winner["qualification_only"]:
        return "blocked_qualification_only_evidence"
    if int(winner["passed"]) < CATEGORY_TASK_TOTAL:
        return "blocked_accuracy_below_category_threshold"
    if int(winner["validation_failures"]) > 0:
        return "blocked_validation_failures_require_review"
    return "promotable_after_policy_review"


def categorize_official_tasks() -> dict[str, Any]:
    suite = load_category_benchmark(CANONICAL_BENCHMARK_PATH)
    matrix: dict[str, dict[str, int]] = {category: {inner: 0 for inner in CANONICAL_CATEGORIES} for category in CANONICAL_CATEGORIES}
    expected_counts = {category: 0 for category in CANONICAL_CATEGORIES}
    predicted_counts = {category: 0 for category in CANONICAL_CATEGORIES}
    misses: list[dict[str, Any]] = []
    official_shape_valid = True
    for task in suite.tasks:
        visible = model_visible_task(task)
        official_shape_valid = official_shape_valid and set(visible) == {"task_id", "prompt"}
        expected = str(task["task_category"])
        family = normalize_task_family(None, visible["prompt"])
        predicted = FAMILY_TO_CATEGORY.get(family, "FACTUAL_KNOWLEDGE")
        matrix[expected][predicted] += 1
        expected_counts[expected] += 1
        predicted_counts[predicted] += 1
        if predicted != expected:
            misses.append(
                {
                    "task_id": visible["task_id"],
                    "expected_category": expected,
                    "predicted_category": predicted,
                    "downstream_risk": "miscategorization_can_route_to_wrong_model_authority",
                }
            )
    total = sum(expected_counts.values())
    correct = sum(matrix[category][category] for category in CANONICAL_CATEGORIES)
    per_category: dict[str, dict[str, float]] = {}
    for category in CANONICAL_CATEGORIES:
        true_positive = matrix[category][category]
        predicted_total = predicted_counts[category]
        expected_total = expected_counts[category]
        per_category[category] = {
            "precision": true_positive / predicted_total if predicted_total else 0,
            "recall": true_positive / expected_total if expected_total else 0,
        }
    return {
        "input_shape": "official_task_array_task_id_prompt_only",
        "official_shape_valid": official_shape_valid,
        "benchmark_metadata_withheld": True,
        "total_tasks": total,
        "correct": correct,
        "accuracy": correct / total if total else 0,
        "confusion_matrix": matrix,
        "per_category": per_category,
        "miscategorized_task_ids": misses,
        "risk_note": "Category classification is high-risk because a wrong category can route a task to the wrong authority.",
    }


def build_work_scope_matrix(overall: list[dict[str, Any]], category_rankings: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    model_ids = [row["id"] for row in overall]
    model_names = {row["id"]: row["display_name"] for row in overall}
    category_by_scope = {scope: category for category, scope in CATEGORY_TO_SCOPE.items()}
    for scope in WORK_SCOPES:
        category = category_by_scope.get(scope)
        entries: list[dict[str, Any]] = []
        for model_id in model_ids:
            category_row = None
            if category:
                category_row = next((row for row in category_rankings[category] if row["id"] == model_id), None)
            if scope in {"TASK_FAMILY_CLASSIFICATION", "ANSWER_SCHEMA_SELECTION", "DETERMINISTIC_VALIDATION", "STRUCTURAL_REPAIR", "TOKEN_BUDGETING"}:
                status = "PENDING_REVIEW"
                reason = "Control-plane scope requires separate reviewed tests; benchmark category evidence is indirect."
            elif scope == "FIREWORKS_FALLBACK":
                status = "FIREWORKS_ONLY"
                reason = "Fallback scope remains Fireworks-only through FIREWORKS_BASE_URL and ALLOWED_MODELS."
            elif category_row and category_row["provider"] in QUALIFICATION_ONLY_PROVIDERS:
                status = "LOCAL_DENIED"
                reason = "Local evidence is qualification-only and not final provider evidence."
            elif category_row and int(category_row["passed"]) == CATEGORY_TASK_TOTAL and int(category_row["validation_failures"]) == 0:
                status = "PENDING_REVIEW"
                reason = "Passing evidence exists, but this artifact does not mutate runtime authorization."
            elif category_row:
                status = "LOCAL_DENIED" if category_row["provider"] in QUALIFICATION_ONLY_PROVIDERS else "PENDING_REVIEW"
                reason = "Current evidence is partial or blocked and cannot promote authority."
            else:
                status = "PENDING_REVIEW"
                reason = "No mapped category evidence."
            entries.append(
                {
                    "model_id": model_id,
                    "model": model_names[model_id],
                    "status": status,
                    "evidence_source": category_row["result_file_name"] if category_row else None,
                    "benchmark_category": category,
                    "reason": reason,
                }
            )
        rows.append({"work_scope": scope, "benchmark_category": category, "models": entries})
    return rows


def build_version5_analytics(results_dir: Path = ROOT / "qualification/results") -> dict[str, Any]:
    result_files = load_result_files(results_dir)
    suite_hash = file_sha256(CANONICAL_BENCHMARK_PATH)
    overall = [overall_metrics(path, payload) for path, payload in result_files]
    per_model_category: dict[str, dict[str, Any]] = {}
    category_rankings: dict[str, list[dict[str, Any]]] = {category: [] for category in CANONICAL_CATEGORIES}
    for path, payload in result_files:
        metrics = per_category_metrics(path, payload)
        identity = result_identity(path, payload)
        per_model_category[identity["id"]] = metrics
        for category, row in metrics.items():
            category_rankings[category].append(row)
    for category in CANONICAL_CATEGORIES:
        category_rankings[category] = sorted(category_rankings[category], key=ranking_key)

    recommendations: dict[str, dict[str, Any]] = {}
    avoid_lists: dict[str, list[dict[str, Any]]] = {}
    tie_break_details: dict[str, list[str]] = {}
    for category, rows in category_rankings.items():
        winner = rows[0] if rows else None
        runner_up = rows[1] if len(rows) > 1 else None
        avoid_lists[category] = [
            {
                "model": row["display_name"],
                "reason": "zero_passes" if int(row["passed"]) == 0 else "qualification_only_or_weaker_than_current_best",
                "passed": row["passed"],
                "tasks": row["tasks"],
            }
            for row in rows
            if int(row["passed"]) == 0 or row["qualification_only"]
        ]
        tie_break_details[category] = [
            "higher passed count",
            "lower judged Fireworks tokens",
            "lower validation failures",
            "lower latency",
            "deterministic identity ordering",
        ]
        if winner:
            recommendations[category] = {
                "recommended": winner["display_name"],
                "recommended_model_id": winner["id"],
                "runner_up": runner_up["display_name"] if runner_up else None,
                "reason": explain_recommendation(category, winner, runner_up, rows),
                "confidence": confidence_for(winner, runner_up),
                "recommendation_status": promotion_status_for(winner),
                "review_status": "reviewed_evidence_only_not_runtime_authorization",
                "local_jurisdiction_certified": False,
            }

    categorization = categorize_official_tasks()
    return {
        "schema": ANALYTICS_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_suite": BENCHMARK_SUITE_ID,
        "benchmark_hash": suite_hash,
        "benchmark_path": str(CANONICAL_BENCHMARK_PATH),
        "source_result_files": [str(path) for path, _ in result_files],
        "per_model_overall_metrics": overall,
        "per_model_per_category_metrics": per_model_category,
        "per_category_ranking": category_rankings,
        "recommended_model_provider_per_category": recommendations,
        "avoid_list_per_category": avoid_lists,
        "tie_break_rules": tie_break_details,
        "work_scope_matrix": build_work_scope_matrix(overall, category_rankings),
        "categorization_evaluation": categorization,
        "promotion_status": "reviewed_evidence_only_not_runtime_authorization",
        "authorization_registry_mutated": False,
        "local_jurisdictions_promoted": [],
        "blockers": [
            "Benchmark runs do not mutate runtime authorization automatically.",
            "No local jurisdiction is LOCAL_CERTIFIED by this artifact.",
            "version5-ollama full 40-task final-provider evidence is still required before local promotion.",
            "Categorization accuracy must be reviewed before authority promotion.",
        ],
    }


def write_version5_analytics(results_dir: Path, output_path: Path) -> dict[str, Any]:
    payload = build_version5_analytics(results_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def build_version6_analytics(results_dir: Path = ROOT / "qualification/results") -> dict[str, Any]:
    evidence = build_version5_analytics(results_dir)
    metrics = evidence["per_model_overall_metrics"]
    local_rows = [row for row in metrics if row["provider"] in {"version6-ollama", "version5-ollama", "ollama-demo"}]
    fallback_rows = [row for row in metrics if row["effective_provider"] == "fireworks" or row["provider"] == "fireworks"]
    compliance = {
        "runtime_contract": {
            "input": "/input/tasks.json",
            "output": "/output/results.json",
            "input_schema": "top_level_array_of_task_id_prompt_records_only",
            "output_schema": "top_level_array_of_task_id_answer_records_only",
            "batch_starts_on_container_start": True,
            "ui_required": False,
            "server_lifecycle_required": False,
        },
        "submission_images": {
            "version6-staging": "submission-shaped_non_submission_staging_fallback",
            "version6-production": "official_submission_fireworks_fallback_only",
        },
        "analytics_ui": {
            "container": "version6-analytics-ui",
            "submission_runtime": False,
            "task_input_form": False,
            "live_execution_endpoint": False,
        },
        "remote_fallback": {
            "production": "FIREWORKS_BASE_URL with FIREWORKS_API_KEY and ALLOWED_MODELS",
            "staging": "STAGING_INFERENCE_BASE_URL for token-safe development only",
            "production_external_non_fireworks_allowed": False,
        },
    }
    deduced = {
        "source": "deterministic_summary_local_narrative_unavailable",
        "fireworks_called": False,
        "summary": (
            "Version 6 keeps the official runtime batch-only, keeps UI and benchmark evidence out of "
            "submission images, and treats accuracy as the gate before Fireworks-token minimization."
        ),
        "recommendation": (
            "Use version6-production for the public submission image after image inspection passes. "
            "Use version6-staging only for production-shaped development tests."
        ),
        "local_nemotron_evidence": {
            "model": "nemotron-3-nano:4b",
            "local_rows": local_rows,
            "narrative_generation": "unavailable_without_running_local_ollama",
        },
    }
    return {
        "schema": VERSION6_ANALYTICS_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_result_files": evidence["source_result_files"],
        "overview": {
            "track": "Track 1 Hybrid Token-Efficient Routing Agent",
            "active_version": "Version 6",
            "team": "team-2168",
            "local_model": "nemotron-3-nano:4b",
            "runtime": "CPU-only Ollama bundled in submission images",
        },
        "results": metrics,
        "category_performance": evidence["per_category_ranking"],
        "route_and_token_flow": {
            "fallback_rows": fallback_rows,
            "judged_fireworks_tokens_by_result": [
                {
                    "result_file": row["result_file_name"],
                    "provider": row["provider"],
                    "effective_provider": row["effective_provider"],
                    "judged_fireworks_tokens": row["judged_fireworks_tokens"],
                }
                for row in metrics
            ],
        },
        "local_nemotron_evidence": local_rows,
        "staging_vs_production_readiness": {
            "same_code_path_required": True,
            "only_remote_fallback_differs": True,
            "staging_not_for_submission": True,
            "production_fireworks_only": True,
        },
        "failures_and_validation": {
            "categorization": evidence["categorization_evaluation"],
            "blockers": [
                *evidence["blockers"],
                "Run image inspection for both Version 6 submission targets before publishing.",
            ],
        },
        "submission_compliance": compliance,
        "deduced_analytics": deduced,
        "authorization_registry_mutated": False,
        "local_jurisdictions_promoted": [],
    }


def write_version6_analytics(results_dir: Path, output_path: Path) -> dict[str, Any]:
    payload = build_version6_analytics(results_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
