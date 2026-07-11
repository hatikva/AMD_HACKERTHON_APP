from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .env import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

WORK_JURISDICTIONS = [
    "TASK_FAMILY_CLASSIFICATION",
    "PROMPT_OPTIMIZATION",
    "TASK_CONTRACT_EXTRACTION",
    "CONTEXT_SELECTION",
    "EVIDENCE_PACKING",
    "ANSWER_SCHEMA_SELECTION",
    "DETERMINISTIC_VALIDATION",
    "REPAIR_CLASSIFICATION",
    "DELTA_REPAIR_PROMPTING",
    "MODEL_ELIGIBILITY_AUDIT",
    "MODEL_SELECTION",
    "TOKEN_BUDGETING",
    "OUTPUT_COMPRESSION",
    "ALLOWED_MODEL_POLICY",
    "FIREWORKS_PROXY_COMPLIANCE",
    "DEMO_LOCAL_MODEL_EXECUTION",
]

VERSION_5_WORK_JURISDICTIONS = [
    "TASK_FAMILY_CLASSIFICATION",
    "PROMPT_OPTIMIZATION",
    "TASK_CONTRACT_EXTRACTION",
    "SHORT_FACTUAL_ANSWERING",
    "SENTIMENT_CLASSIFICATION",
    "NAMED_ENTITY_RECOGNITION",
    "SIMPLE_SUMMARIZATION",
    "MATH_LIGHT",
    "LOGICAL_DEDUCTION_LIGHT",
    "CODE_DEBUGGING_SMALL",
    "CODE_GENERATION_SMALL",
    "ANSWER_SCHEMA_SELECTION",
    "DETERMINISTIC_VALIDATION",
    "STRUCTURAL_REPAIR",
    "SEMANTIC_REPAIR",
    "FIREWORKS_FALLBACK",
    "TOKEN_BUDGETING",
]

LOCAL_STATUS_VALUES = {"LOCAL_CERTIFIED", "LOCAL_DENIED", "LOCAL_CONDITIONAL", "FIREWORKS_ONLY"}
VERSION_5_LOCAL_PROVIDER = "version5-ollama"
VERSION_6_LOCAL_PROVIDER = "version6-ollama"
VERSION_6_PRODUCTION_PROVIDER = "version6-production"
VERSION_6_STAGING_PROVIDER = "version6-staging"
VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER = "version6-staging-remote-baseline"
VERSION_6_POLICY_SCHEMA = "amd_hackathon.version6.routing_policy.v1"
VERSION_6_POLICY_REQUIRED_PROVIDERS = {VERSION_6_PRODUCTION_PROVIDER, VERSION_6_STAGING_PROVIDER}
VERSION_6_DEFAULT_POLICY_FILES = {
    VERSION_6_PRODUCTION_PROVIDER: "version6_routing_policy.json",
    VERSION_6_STAGING_PROVIDER: "version6_staging_authorizations.json",
}
VERSION_5_LOCAL_PROVIDERS = {VERSION_5_LOCAL_PROVIDER, "llama-cpp"}
VERSION_6_PROVIDERS = {VERSION_6_PRODUCTION_PROVIDER, VERSION_6_STAGING_PROVIDER}
LOCAL_OLLAMA_PROVIDERS = {VERSION_5_LOCAL_PROVIDER, VERSION_6_LOCAL_PROVIDER}
STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD = "ollama-cloud"
OLLAMA_CLOUD_MODEL_MAPPINGS = {
    "minimax-m3:cloud": {
        "api_model_id": "minimax-m3",
        "mapping_status": "VERIFIED_FROM_API_TAGS",
        "direct_smoke_status": "STAGING_MODEL_VERIFIED",
    },
    "nemotron-3-super:cloud": {
        "api_model_id": "nemotron-3-super",
        "mapping_status": "VERIFIED_FROM_API_TAGS",
        "direct_smoke_status": "STAGING_MODEL_UNAVAILABLE_TIMEOUT",
    },
    "gpt-oss:20b-cloud": {
        "api_model_id": "gpt-oss:20b",
        "mapping_status": "VERIFIED_FROM_API_TAGS",
        "direct_smoke_status": "STAGING_MODEL_VERIFIED",
    },
    "gemma4:31b-cloud": {
        "api_model_id": "gemma4:31b",
        "mapping_status": "VERIFIED_FROM_API_TAGS",
        "direct_smoke_status": "STAGING_MODEL_VERIFIED",
    },
}

VERSION_6_MODE = {
    "track": "AMD Developer Hackathon ACT II Track 1",
    "team": "team-2168",
    "team_members": 1,
    "contact": "dr.wbsite@gmail.com",
    "timeline": {
        "start": "2026-07-06 16:00 British Summer Time",
        "end": "2026-07-12 16:00 British Summer Time",
    },
    "production_remote_fallback": "fireworks",
    "staging_remote_fallback": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
    "staging_status": "NOT_FOR_SUBMISSION",
}

VERSION_5_LOCAL_MODEL = {
    "model_name": "nemotron-3-nano:4b",
    "file_name": "nemotron-3-nano-4b.gguf",
    "image_path": "/app/models/nemotron-3-nano-4b.gguf",
    "sha256": "527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970",
    "size_bytes": 2837586496,
    "source": "local Ollama GGUF backup",
    "backup_path": "/mnt/g/ollama-models-backup-container/models/blobs/sha256-527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970",
    "format": "GGUF",
    "quantization": "observed_ollama_model_blob",
    "license": "from bundled Ollama license layer; review before final submission",
}

VERSION_5_RUNTIME_CERTIFICATION = {
    "version_5_local_runtime": "OLLAMA_CERTIFIED",
    "local_runtime_model": "nemotron-3-nano:4b",
    "local_runtime_provider": VERSION_5_LOCAL_PROVIDER,
    "local_runtime_image_status": "SELF_CONTAINED_UNDER_10GB",
    "local_runtime_memory_status": "PASSED_4GB_2VCPU_SMOKE",
    "compressed_image_bytes": 2866482542,
    "constrained_smoke": {
        "memory": "4g",
        "cpus": 2,
        "answer": "4",
        "oom_killed": False,
        "elapsed_seconds": 19.98,
    },
    "jurisdiction_authorization": "evidence_bound_by_VERSION_5_LOCAL_CERTIFICATION",
}

VERSION_5_LOCAL_CERTIFICATION = {
    "TASK_FAMILY_CLASSIFICATION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_BENCHMARK_PROMOTION",
        "validator_coverage": "medium",
    },
    "PROMPT_OPTIMIZATION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_BENCHMARK_PROMOTION",
        "validator_coverage": "medium",
    },
    "TASK_CONTRACT_EXTRACTION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_BENCHMARK_PROMOTION",
        "validator_coverage": "medium",
    },
    "SHORT_FACTUAL_ANSWERING": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "SENTIMENT_CLASSIFICATION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_BENCHMARK_PROMOTION",
        "validator_coverage": "high",
    },
    "NAMED_ENTITY_RECOGNITION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_BENCHMARK_PROMOTION",
        "validator_coverage": "medium",
    },
    "SIMPLE_SUMMARIZATION": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "MATH_LIGHT": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "medium",
    },
    "LOGICAL_DEDUCTION_LIGHT": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "CODE_DEBUGGING_SMALL": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "CODE_GENERATION_SMALL": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "ANSWER_SCHEMA_SELECTION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_BENCHMARK_PROMOTION",
        "validator_coverage": "high",
    },
    "DETERMINISTIC_VALIDATION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "DETERMINISTIC_CODE_ONLY",
        "validator_coverage": "high",
    },
    "STRUCTURAL_REPAIR": {
        "local_status": "LOCAL_DENIED",
        "fallback": "DETERMINISTIC_REPAIR_OR_FIREWORKS",
        "validator_coverage": "high",
    },
    "SEMANTIC_REPAIR": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "FIREWORKS_FALLBACK": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "not_applicable",
    },
    "TOKEN_BUDGETING": {
        "local_status": "LOCAL_DENIED",
        "fallback": "DETERMINISTIC_CODE_ONLY",
        "validator_coverage": "high",
    },
}

TASK_FAMILIES = {
    "factual_qa",
    "math_reasoning",
    "sentiment",
    "summarization",
    "named_entity_recognition",
    "code_debugging",
    "logic_puzzles",
    "code_generation",
}


@dataclass(frozen=True)
class Scenario:
    id: str
    task_family: str
    prompt: str
    expected_format: str
    difficulty_hint: int = 1
    evidence_refs: list[str] | None = None


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    task_family: str | None = None
    expected_format: str = "text"
    evidence_refs: list[str] | None = None
    source: str = "internal"


@dataclass(frozen=True)
class RouteDecision:
    provider: str
    model: str
    jurisdiction: str
    reason: str
    final_mode_compliant: bool
    candidate_version: str = "version_3"
    selected_path: str = "fireworks"
    local_certification: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderResult:
    text: str
    token_usage: dict[str, Any]
    latency_ms: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) + len(text) // 16)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_scenarios(path: Path = ROOT / "benchmarks/scenarios.json") -> dict[str, Scenario]:
    rows = load_json(path)
    return {row["id"]: Scenario(**row) for row in rows}


def parse_allowed_models(value: str | None = None) -> list[str]:
    raw = value if value is not None else os.environ.get("ALLOWED_MODELS", "")
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        parsed = json.loads(raw)
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


def parse_staging_allowed_models(value: str | None = None) -> list[str]:
    raw = value if value is not None else os.environ.get("STAGING_ALLOWED_MODELS", "")
    return parse_allowed_models(raw)


def resolve_ollama_cloud_model(supplied_id: str, allowed_models: list[str]) -> str:
    if not supplied_id:
        raise RuntimeError("STAGING_INFERENCE_MODEL is required for Version 6 Ollama Cloud staging")
    if not allowed_models:
        raise RuntimeError("STAGING_ALLOWED_MODELS is required for Version 6 Ollama Cloud staging")
    if supplied_id not in allowed_models:
        raise RuntimeError(f"STAGING_INFERENCE_MODEL {supplied_id} is not present in STAGING_ALLOWED_MODELS")
    mapping = OLLAMA_CLOUD_MODEL_MAPPINGS.get(supplied_id)
    if not mapping or mapping.get("mapping_status") != "VERIFIED_FROM_API_TAGS":
        raise RuntimeError(f"Ollama Cloud model {supplied_id} has not been verified through /api/tags")
    return str(mapping["api_model_id"])


def version6_policy_mode(provider_name: str) -> str:
    if provider_name == VERSION_6_PRODUCTION_PROVIDER:
        return "production"
    if provider_name == VERSION_6_STAGING_PROVIDER:
        return "staging"
    raise ValueError(f"provider does not require a Version 6 policy: {provider_name}")


def policy_file_path(provider_name: str) -> Path:
    env_name = "VERSION6_PRODUCTION_POLICY_PATH" if provider_name == VERSION_6_PRODUCTION_PROVIDER else "VERSION6_STAGING_POLICY_PATH"
    explicit = os.environ.get(env_name) or os.environ.get("VERSION6_ROUTING_POLICY_PATH")
    if explicit:
        return Path(explicit)
    filename = VERSION_6_DEFAULT_POLICY_FILES[provider_name]
    try:
        return Path(str(resources.files("amd_hackathon_app").joinpath("authorization", filename)))
    except ModuleNotFoundError:
        return ROOT / "src" / "amd_hackathon_app" / "authorization" / filename


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"version6 policy field {field} must be a non-empty string")
    return value


def validate_version6_policy(payload: dict[str, Any], expected_mode: str) -> dict[str, Any]:
    required_fields = {
        "schema",
        "policy_id",
        "generated_at",
        "policy_mode",
        "source_calibration_artifact_hash",
        "threshold_config_hash",
        "official_fireworks_token_score_status",
        "category_routes",
        "work_scope_routes",
        "fallback_routes",
        "failed_or_denied_routes",
        "allowed_model_source",
        "provider_boundary",
    }
    missing = sorted(required_fields - set(payload))
    if missing:
        raise ValueError(f"version6 policy missing required fields: {', '.join(missing)}")
    if payload["schema"] != VERSION_6_POLICY_SCHEMA:
        raise ValueError(f"unsupported version6 policy schema: {payload['schema']}")
    if payload["policy_mode"] != expected_mode:
        raise ValueError(f"version6 policy mode {payload['policy_mode']} does not match {expected_mode}")
    _require_string(payload, "policy_id")
    _require_string(payload, "generated_at")
    _require_string(payload, "source_calibration_artifact_hash")
    _require_string(payload, "threshold_config_hash")
    _require_string(payload, "official_fireworks_token_score_status")
    _require_string(payload, "allowed_model_source")
    _require_string(payload, "provider_boundary")
    for field in ["category_routes", "work_scope_routes", "fallback_routes", "failed_or_denied_routes"]:
        if not isinstance(payload.get(field), dict):
            raise ValueError(f"version6 policy field {field} must be an object")

    for section in ["category_routes", "work_scope_routes"]:
        for key, route in payload[section].items():
            if not isinstance(route, dict):
                raise ValueError(f"version6 policy {section}.{key} must be an object")
            for field in [
                "selected_provider",
                "selected_model",
                "runner_up_provider",
                "runner_up_model",
                "authorization_status",
                "required_gates_passed",
                "fallback_policy",
            ]:
                if field not in route:
                    raise ValueError(f"version6 policy {section}.{key} missing {field}")
            if route["authorization_status"] not in {"authorized", "fallback_only", "denied"}:
                raise ValueError(f"version6 policy {section}.{key} has invalid authorization_status")
            if not isinstance(route["required_gates_passed"], bool):
                raise ValueError(f"version6 policy {section}.{key}.required_gates_passed must be boolean")
    return payload


def load_version6_policy(provider_name: str) -> dict[str, Any]:
    if provider_name not in VERSION_6_POLICY_REQUIRED_PROVIDERS:
        raise ValueError(f"provider does not require a Version 6 policy: {provider_name}")
    path = policy_file_path(provider_name)
    if not path.is_file():
        raise RuntimeError(f"required Version 6 routing policy is missing for {provider_name}: {path}")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Version 6 routing policy must be a JSON object: {path}")
    try:
        return validate_version6_policy(payload, version6_policy_mode(provider_name))
    except ValueError as exc:
        raise RuntimeError(f"Version 6 routing policy is invalid for {provider_name}: {exc}") from exc


def category_for_task_family(task_family: str) -> str:
    mapping = {
        "factual_qa": "FACTUAL_KNOWLEDGE",
        "math_reasoning": "MATHEMATICAL_REASONING",
        "sentiment": "SENTIMENT_CLASSIFICATION",
        "summarization": "TEXT_SUMMARISATION",
        "named_entity_recognition": "NAMED_ENTITY_RECOGNITION",
        "code_debugging": "CODE_DEBUGGING",
        "logic_puzzles": "LOGICAL_DEDUCTIVE_REASONING",
        "code_generation": "CODE_GENERATION",
    }
    return mapping.get(task_family, "FACTUAL_KNOWLEDGE")


def _policy_route_authorized(route: dict[str, Any] | None) -> bool:
    return bool(route and route.get("authorization_status") == "authorized" and route.get("required_gates_passed") is True)


def _fallback_route(policy: dict[str, Any], route: dict[str, Any] | None, provider_name: str) -> dict[str, Any] | None:
    fallback_id = str((route or {}).get("fallback_policy") or "default")
    fallbacks = policy.get("fallback_routes") or {}
    fallback = fallbacks.get(fallback_id) or fallbacks.get("default")
    if isinstance(fallback, dict):
        return fallback
    if provider_name == VERSION_6_PRODUCTION_PROVIDER:
        return {"selected_provider": "fireworks", "selected_model": "$ALLOWED_MODELS_FIRST"}
    return None


def _resolve_policy_model(provider_name: str, model: str, allowed_models: list[str]) -> str:
    if provider_name == "fireworks":
        if model == "$ALLOWED_MODELS_FIRST":
            if not allowed_models:
                raise RuntimeError("ALLOWED_MODELS is required for Version 6 production policy fallback")
            return allowed_models[0]
        if model not in allowed_models:
            raise RuntimeError(f"Version 6 production policy selected model not present in ALLOWED_MODELS: {model}")
        return model
    if provider_name == VERSION_6_STAGING_PROVIDER:
        return resolve_ollama_cloud_model(model, parse_staging_allowed_models())
    return model


def policy_route_decision(
    provider_name: str,
    task_family: str,
    jurisdiction: str,
    allowed_models: list[str],
) -> tuple[str, str, str, dict[str, Any]]:
    policy = load_version6_policy(provider_name)
    category = category_for_task_family(task_family)
    category_route = policy["category_routes"].get(category)
    scope_route = policy["work_scope_routes"].get(jurisdiction)
    selected_route = category_route if _policy_route_authorized(category_route) else scope_route
    if not _policy_route_authorized(selected_route):
        selected_route = _fallback_route(policy, category_route or scope_route, provider_name)
    if not isinstance(selected_route, dict):
        raise RuntimeError(f"Version 6 policy has no authorized or fallback route for {category}/{jurisdiction}")

    selected_provider = str(selected_route.get("selected_provider", "")).strip()
    selected_model = str(selected_route.get("selected_model", "")).strip()
    if not selected_provider or not selected_model:
        raise RuntimeError(f"Version 6 policy route is missing selected provider/model for {category}/{jurisdiction}")
    if provider_name == VERSION_6_PRODUCTION_PROVIDER and selected_provider in {VERSION_6_STAGING_PROVIDER, VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER, STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD}:
        raise RuntimeError("Version 6 production policy cannot route to staging or Ollama Cloud providers")
    if selected_provider == "mock" and os.environ.get("AMD_POLICY_TEST_ALLOW_MOCK") != "1":
        raise RuntimeError("Version 6 policy cannot route to mock outside tests")
    resolved_model = _resolve_policy_model(selected_provider, selected_model, allowed_models)
    route_status = "policy_authorized" if _policy_route_authorized(selected_route) else "policy_fallback"
    audit = {
        "policy_id": policy["policy_id"],
        "policy_mode": policy["policy_mode"],
        "policy_schema": policy["schema"],
        "policy_source_hash": policy["source_calibration_artifact_hash"],
        "threshold_config_hash": policy["threshold_config_hash"],
        "category": category,
        "work_scope": jurisdiction,
        "authorization_status": selected_route.get("authorization_status", "fallback"),
        "route_status": route_status,
    }
    return selected_provider, resolved_model, route_status, audit


def task_from_mapping(row: dict[str, Any], fallback_id: str) -> Task:
    prompt = row.get("prompt") or row.get("input") or row.get("question") or row.get("task")
    if not prompt:
        raise ValueError(f"task {fallback_id} is missing prompt/input/question/task text")
    task_family = row.get("task_family") or row.get("category") or row.get("type")
    evidence_refs = row.get("evidence_refs") or []
    return Task(
        id=str(row.get("id") or fallback_id),
        prompt=str(prompt),
        task_family=str(task_family) if task_family else None,
        expected_format=str(row.get("expected_format") or row.get("format") or "text"),
        evidence_refs=[str(item) for item in evidence_refs],
    )


def submission_task_from_mapping(row: dict[str, Any], fallback_id: str) -> Task:
    if not isinstance(row, dict):
        raise ValueError(f"task {fallback_id} must be an object")
    if set(row) != {"task_id", "prompt"}:
        raise ValueError(f"task {fallback_id} must contain only task_id and prompt")
    task_id = row.get("task_id")
    prompt = row.get("prompt")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError(f"task {fallback_id} is missing required string task_id")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f"task {task_id} is missing required string prompt")
    return Task(
        id=task_id,
        prompt=prompt,
        task_family=None,
        expected_format="text",
        evidence_refs=[],
        source="submission_input",
    )


def load_tasks(path: Path) -> list[Task]:
    payload = load_json(path)
    rows = payload.get("tasks", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("tasks input must be a list or an object with a tasks list")
    return [task_from_mapping(row, f"task-{index + 1}") for index, row in enumerate(rows)]


def load_submission_tasks(path: Path) -> list[Task]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ValueError("official tasks input must be a top-level list")
    return [submission_task_from_mapping(row, f"task-{index + 1}") for index, row in enumerate(payload)]


def scenario_to_task(scenario: Scenario) -> Task:
    return Task(
        id=scenario.id,
        prompt=scenario.prompt,
        task_family=scenario.task_family,
        expected_format=scenario.expected_format,
        evidence_refs=scenario.evidence_refs or [],
    )


def normalize_task_family(value: str | None, prompt: str) -> str:
    if value:
        normalized = value.lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "qa": "factual_qa",
            "factual": "factual_qa",
            "math": "math_reasoning",
            "ner": "named_entity_recognition",
            "debugging": "code_debugging",
            "logic": "logic_puzzles",
            "reasoning": "logic_puzzles",
            "code": "code_generation",
            "classification": "factual_qa",
            "json_extraction": "named_entity_recognition",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in TASK_FAMILIES:
            return normalized

    lower_prompt = prompt.lower()
    if any(term in lower_prompt for term in ["sentiment", "positive", "negative", "neutral"]):
        return "sentiment"
    if any(term in lower_prompt for term in ["summarize", "summary", "tl;dr"]):
        return "summarization"
    if any(term in lower_prompt for term in ["extract entities", "named entities", "ner"]):
        return "named_entity_recognition"
    if any(term in lower_prompt for term in ["bug", "traceback", "fix this code", "debug"]):
        return "code_debugging"
    if any(term in lower_prompt for term in ["write code", "implement", "function", "class"]):
        return "code_generation"
    if any(term in lower_prompt for term in ["solve", "prove", "logic puzzle"]):
        return "logic_puzzles"
    if any(term in lower_prompt for term in ["calculate", "equation", "sum", "product"]):
        return "math_reasoning"
    return "factual_qa"


def jurisdiction_for(task_family: str, provider_override: str | None = None) -> str:
    if provider_override == "ollama-demo":
        return "DEMO_LOCAL_MODEL_EXECUTION"
    if provider_override == VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER:
        return "STAGING_REMOTE_BASELINE"
    if provider_override in {"version5", VERSION_5_LOCAL_PROVIDER, "llama-cpp", *VERSION_6_PROVIDERS, VERSION_6_LOCAL_PROVIDER}:
        return version5_jurisdiction_for(task_family)
    if task_family in {"sentiment", "named_entity_recognition"}:
        return "ANSWER_SCHEMA_SELECTION"
    if task_family in {"summarization", "factual_qa"}:
        return "CONTEXT_SELECTION"
    if task_family in {"code_debugging", "code_generation"}:
        return "PROMPT_OPTIMIZATION"
    if task_family in {"math_reasoning", "logic_puzzles"}:
        return "TASK_CONTRACT_EXTRACTION"
    return "TASK_FAMILY_CLASSIFICATION"


def version5_jurisdiction_for(task_family: str) -> str:
    mapping = {
        "factual_qa": "SHORT_FACTUAL_ANSWERING",
        "math_reasoning": "MATH_LIGHT",
        "sentiment": "SENTIMENT_CLASSIFICATION",
        "summarization": "SIMPLE_SUMMARIZATION",
        "named_entity_recognition": "NAMED_ENTITY_RECOGNITION",
        "code_debugging": "CODE_DEBUGGING_SMALL",
        "logic_puzzles": "LOGICAL_DEDUCTION_LIGHT",
        "code_generation": "CODE_GENERATION_SMALL",
    }
    return mapping.get(task_family, "TASK_FAMILY_CLASSIFICATION")


def local_certification_for(jurisdiction: str) -> dict[str, Any]:
    row = VERSION_5_LOCAL_CERTIFICATION.get(
        jurisdiction,
        {
            "local_status": "FIREWORKS_ONLY",
            "fallback": "FIREWORKS_REQUIRED",
            "validator_coverage": "unknown",
        },
    )
    status = str(row["local_status"])
    if status not in LOCAL_STATUS_VALUES:
        raise ValueError(f"invalid local certification status for {jurisdiction}: {status}")
    return {
        "jurisdiction_id": jurisdiction,
        "local_status": status,
        "local_model": os.environ.get("OLLAMA_MODEL_NAME", VERSION_5_LOCAL_MODEL["model_name"]),
        "local_model_sha256": VERSION_5_LOCAL_MODEL["sha256"],
        "runtime_certification": VERSION_5_RUNTIME_CERTIFICATION["version_5_local_runtime"],
        "local_runtime_provider": VERSION_5_LOCAL_PROVIDER,
        "local_threshold": None,
        "validator_coverage": row["validator_coverage"],
        "fallback": row["fallback"],
        "fireworks_policy": "ALLOWED_MODELS_ONLY",
        "benchmark_status": "selected_model_pending_real_benchmark_promotion",
    }


def select_answer_schema(task_family: str, expected_format: str) -> dict[str, Any]:
    if expected_format == "json" or task_family in {"sentiment", "named_entity_recognition"}:
        return {
            "format": "json",
            "instruction": "Return only valid JSON. Do not include markdown fences.",
        }
    return {
        "format": "text",
        "instruction": "Return a concise answer with no preamble.",
    }


def retrieve_context(task: Task, max_refs: int = 3) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for ref in (task.evidence_refs or [])[:max_refs]:
        path = ROOT / ref
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        refs.append({"ref": ref, "content": content})
    return refs


def compile_execution_packet(
    task: Task,
    task_family: str,
    jurisdiction: str,
) -> dict[str, Any]:
    schema = select_answer_schema(task_family, task.expected_format)
    refs = retrieve_context(task)
    evidence_text = "\n\n".join(f"[{row['ref']}]\n{row['content']}" for row in refs) or "No external evidence supplied."
    compiled_prompt = (
        "You are solving an AMD Developer Hackathon Track 1 task.\n"
        "Follow the task contract exactly and minimize unnecessary output tokens.\n\n"
        f"Task family: {task_family}\n"
        f"Work jurisdiction: {jurisdiction}\n"
        f"Answer schema: {schema['instruction']}\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        f"Task:\n{task.prompt}"
    )
    return {
        "task_id": task.id,
        "task_family": task_family,
        "work_jurisdiction": jurisdiction,
        "answer_schema": schema,
        "selected_evidence_refs": [row["ref"] for row in refs],
        "omitted_context_reason": "within_budget" if refs else "no_external_evidence",
        "compiled_prompt": compiled_prompt,
        "estimated_input_tokens": estimate_tokens(compiled_prompt),
        "token_budget": {
            "preferred_context_tokens": 2048,
            "max_completion_tokens": 512,
        },
    }


def select_model(allowed_models: list[str], provider_name: str) -> str:
    if provider_name == "mock":
        return "mock-model"
    if provider_name == "ollama-demo":
        return os.environ.get("MODEL_NAME", "qwen2.5-coder:3b")
    if provider_name in LOCAL_OLLAMA_PROVIDERS:
        return os.environ.get("OLLAMA_MODEL_NAME", VERSION_5_LOCAL_MODEL["model_name"])
    if provider_name in {VERSION_6_STAGING_PROVIDER, VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER}:
        supplied_id = os.environ.get("STAGING_INFERENCE_MODEL", "").strip()
        staging_allowed = parse_staging_allowed_models()
        return resolve_ollama_cloud_model(supplied_id, staging_allowed)
    if provider_name == "llama-cpp":
        return os.environ.get("LLAMA_MODEL_PATH", VERSION_5_LOCAL_MODEL["image_path"])
    if not allowed_models:
        raise RuntimeError("ALLOWED_MODELS is required for Fireworks execution")
    return allowed_models[0]


def route_task(
    task_family: str,
    jurisdiction: str,
    provider_override: str | None = None,
    allowed_models: list[str] | None = None,
) -> RouteDecision:
    provider_name = provider_override or "fireworks"
    allowed = allowed_models if allowed_models is not None else parse_allowed_models()
    if provider_name not in {
        "mock",
        "fireworks",
        "ollama-demo",
        "version5",
        VERSION_5_LOCAL_PROVIDER,
        VERSION_6_LOCAL_PROVIDER,
        VERSION_6_PRODUCTION_PROVIDER,
        VERSION_6_STAGING_PROVIDER,
        VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
        "llama-cpp",
    }:
        raise ValueError(f"unknown provider override: {provider_name}")
    local_certification = None
    candidate_version = "version_3"
    selected_path = provider_name
    if provider_name == "version5":
        candidate_version = "version_5"
        local_certification = local_certification_for(jurisdiction)
        if local_certification["local_status"] == "LOCAL_CERTIFIED":
            provider_name = VERSION_5_LOCAL_PROVIDER
            selected_path = "local"
        else:
            provider_name = "fireworks"
            selected_path = "fireworks"
    elif provider_name in VERSION_5_LOCAL_PROVIDERS:
        candidate_version = "version_5"
        local_certification = local_certification_for(jurisdiction)
        selected_path = (
            "local_final_candidate_benchmark"
            if provider_name == VERSION_5_LOCAL_PROVIDER
            else "local_rejected_runtime_evidence"
        )
    elif provider_name in VERSION_6_PROVIDERS:
        candidate_version = "version_6"
        local_certification = local_certification_for(jurisdiction)
        provider_name, policy_model, selected_path, policy_audit = policy_route_decision(
            provider_name,
            task_family,
            jurisdiction,
            allowed,
        )
        model = policy_model
        final_mode_compliant = provider_name in {"fireworks", VERSION_6_LOCAL_PROVIDER}
        return RouteDecision(
            provider=provider_name,
            model=model,
            jurisdiction=jurisdiction,
            reason="version_6_compact_policy",
            final_mode_compliant=final_mode_compliant,
            candidate_version=candidate_version,
            selected_path=selected_path,
            local_certification=local_certification,
            policy=policy_audit,
        )
    elif provider_name == VERSION_6_LOCAL_PROVIDER:
        candidate_version = "version_6"
        local_certification = local_certification_for(jurisdiction)
        selected_path = "local_direct_runtime_evidence"
    elif provider_name == VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER:
        candidate_version = "version_6"
        selected_path = "staging_remote_baseline"
    model = select_model(allowed, provider_name)
    final_mode_compliant = provider_name in {"fireworks", "mock", VERSION_5_LOCAL_PROVIDER, VERSION_6_LOCAL_PROVIDER}
    if provider_name == "ollama-demo":
        reason = "demo_local_model_execution"
    elif provider_name == VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER:
        reason = "staging_remote_baseline_direct_ollama_cloud"
    elif candidate_version == "version_6":
        reason = "version_6_local_certification_lookup"
    elif candidate_version == "version_5":
        reason = "version_5_local_certification_lookup"
    else:
        reason = "jurisdiction_threshold_model_selection"
    return RouteDecision(
        provider=provider_name,
        model=model,
        jurisdiction=jurisdiction,
        reason=reason,
        final_mode_compliant=final_mode_compliant,
        candidate_version=candidate_version,
        selected_path=selected_path,
        local_certification=local_certification,
    )


class MockProvider:
    name = "mock"

    def complete(self, prompt: str, model: str) -> ProviderResult:
        start = time.perf_counter()
        if "Return only valid JSON" in prompt:
            if "sentiment" in prompt:
                text = '{"label":"neutral","confidence":0.74}'
            else:
                text = '{"answer":"Hatikva","track":"AMD Hackathon Track 1"}'
        elif "summarization" in prompt:
            text = "Concise summary generated by the mock provider."
        else:
            text = "Deterministic routing selected a compact answer path for this task."
        return ProviderResult(
            text=text,
            token_usage={
                "prompt_tokens": estimate_tokens(prompt),
                "completion_tokens": estimate_tokens(text),
                "total_tokens": estimate_tokens(prompt) + estimate_tokens(text),
            },
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = int(os.environ.get("FIREWORKS_MAX_RETRIES", "4"))
        self.retry_backoff_seconds = float(os.environ.get("FIREWORKS_RETRY_BACKOFF_SECONDS", "2"))
        self.timeout_seconds = int(os.environ.get("FIREWORKS_TIMEOUT_SECONDS", "300"))

    def complete(self, prompt: str, model: str) -> ProviderResult:
        start = time.perf_counter()
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code != 429 or attempt >= self.max_retries:
                    raise RuntimeError(f"provider request failed for {self.base_url}: {exc}") from exc
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self.retry_backoff_seconds * (attempt + 1)
                time.sleep(delay)
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"provider request failed for {self.base_url}: {exc}") from exc
                time.sleep(self.retry_backoff_seconds * (attempt + 1))
            except TimeoutError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"provider request timed out for {self.base_url}: {exc}") from exc
                time.sleep(self.retry_backoff_seconds * (attempt + 1))
        else:
            raise RuntimeError(f"provider request failed for {self.base_url}: {last_error}")

        choice = payload["choices"][0]
        message = choice.get("message") or {}
        text = message.get("content") or message.get("reasoning") or choice.get("text") or ""
        if isinstance(text, list):
            text = "".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in text)
        text = str(text)
        usage = payload.get("usage") or {}
        return ProviderResult(
            text=text,
            token_usage={
                "prompt_tokens": int(usage.get("prompt_tokens", estimate_tokens(prompt))),
                "completion_tokens": int(usage.get("completion_tokens", estimate_tokens(text))),
                "total_tokens": int(usage.get("total_tokens", estimate_tokens(prompt) + estimate_tokens(text))),
            },
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


class OllamaLocalProvider(OpenAICompatibleProvider):
    name = VERSION_6_LOCAL_PROVIDER

    def __init__(self) -> None:
        super().__init__(
            os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            api_key=os.environ.get("OLLAMA_API_KEY"),
        )
        self.timeout_seconds = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))

    def complete(self, prompt: str, model: str) -> ProviderResult:
        result = super().complete(prompt, model)
        return ProviderResult(
            text=result.text,
            token_usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "local_prompt_estimate": estimate_tokens(prompt),
                "local_completion_estimate": estimate_tokens(result.text),
            },
            latency_ms=result.latency_ms,
        )


class OllamaCloudStagingProvider:
    name = VERSION_6_STAGING_PROVIDER

    def __init__(self) -> None:
        remote_fallback = os.environ.get("VERSION6_REMOTE_FALLBACK")
        staging_provider = os.environ.get("STAGING_REMOTE_PROVIDER")
        if remote_fallback != "staging" or staging_provider != STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD:
            raise RuntimeError(
                "Ollama Cloud staging provider requires VERSION6_REMOTE_FALLBACK=staging "
                "and STAGING_REMOTE_PROVIDER=ollama-cloud"
            )
        self.base_url = os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://ollama.com").rstrip("/")
        self.api_key = os.environ.get("OLLAMA_API_KEY")
        if not self.api_key:
            raise RuntimeError("OLLAMA_API_KEY is required for Ollama Cloud staging")
        self.max_retries = int(os.environ.get("STAGING_MAX_RETRIES", "2"))
        self.retry_backoff_seconds = float(os.environ.get("STAGING_RETRY_BACKOFF_SECONDS", "2"))
        self.timeout_seconds = int(os.environ.get("STAGING_TIMEOUT_SECONDS", "180"))

    def complete(self, prompt: str, model: str) -> ProviderResult:
        start = time.perf_counter()
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        last_error: Exception | None = None
        payload: dict[str, Any] | None = None
        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    raise RuntimeError(f"Ollama Cloud staging request failed with HTTP {exc.code}") from exc
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self.retry_backoff_seconds * (attempt + 1)
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Ollama Cloud staging request failed: {type(exc).__name__}") from exc
                time.sleep(self.retry_backoff_seconds * (attempt + 1))
        else:
            raise RuntimeError(f"Ollama Cloud staging request failed: {last_error}")

        if not isinstance(payload, dict):
            raise RuntimeError("Ollama Cloud staging response was malformed")
        message = payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama Cloud staging response was missing message")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Ollama Cloud staging response was empty")

        prompt_count = payload.get("prompt_eval_count")
        completion_count = payload.get("eval_count")
        token_usage: dict[str, Any] = {
            "judged_fireworks_tokens": "not_applicable",
            "official_fireworks_token_score": "NOT_MEASURED",
            "staging_remote_provider": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
            "staging_remote_model": model,
            "staging_remote_total_duration": payload.get("total_duration"),
            "staging_remote_load_duration": payload.get("load_duration"),
            "staging_remote_eval_duration": payload.get("eval_duration"),
            "retry_count": 0,
        }
        if isinstance(prompt_count, int):
            token_usage["staging_remote_prompt_tokens"] = prompt_count
        if isinstance(completion_count, int):
            token_usage["staging_remote_completion_tokens"] = completion_count
        if isinstance(prompt_count, int) and isinstance(completion_count, int):
            token_usage["staging_remote_total_tokens"] = prompt_count + completion_count

        return ProviderResult(
            text=text,
            token_usage=token_usage,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


class LlamaCppProvider:
    name = "llama-cpp"

    def __init__(self) -> None:
        self.binary = os.environ.get("LLAMA_CPP_BINARY", "/app/bin/llama-cli")
        self.context_length = int(os.environ.get("LLAMA_CONTEXT_LENGTH", "2048"))
        self.threads = int(os.environ.get("LLAMA_THREADS", "2"))
        self.max_tokens = int(os.environ.get("LLAMA_MAX_TOKENS", "128"))
        self.timeout_seconds = int(os.environ.get("LLAMA_TIMEOUT_SECONDS", "60"))

    def command_for(self, prompt: str, model: str) -> list[str]:
        return [
            self.binary,
            "-m",
            model,
            "-p",
            prompt,
            "-n",
            str(self.max_tokens),
            "-c",
            str(self.context_length),
            "-t",
            str(self.threads),
        ]

    def complete(self, prompt: str, model: str) -> ProviderResult:
        start = time.perf_counter()
        if not Path(self.binary).exists():
            raise RuntimeError(f"llama.cpp binary not found: {self.binary}")
        if not Path(model).exists():
            raise RuntimeError(f"GGUF model not found: {model}")
        command = self.command_for(prompt, model)
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"llama.cpp timed out after {self.timeout_seconds}s") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()[:500]
            raise RuntimeError(f"llama.cpp exited with {completed.returncode}: {stderr}")
        text = completed.stdout.decode("utf-8", errors="replace").strip()
        return ProviderResult(
            text=text,
            token_usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "local_prompt_estimate": estimate_tokens(prompt),
                "local_completion_estimate": estimate_tokens(text),
            },
            latency_ms=int((time.perf_counter() - start) * 1000),
        )


def provider_for(name: str) -> Any:
    if name == "mock":
        return MockProvider()
    if name == "ollama-demo":
        return OpenAICompatibleProvider(os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"))
    if name in LOCAL_OLLAMA_PROVIDERS:
        return OllamaLocalProvider()
    if name in {VERSION_6_STAGING_PROVIDER, VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER}:
        return OllamaCloudStagingProvider()
    if name == "fireworks":
        api_key = os.environ.get("FIREWORKS_API_KEY")
        if not api_key:
            raise RuntimeError("FIREWORKS_API_KEY is required for Fireworks execution")
        base_url = os.environ.get("FIREWORKS_BASE_URL")
        if not base_url:
            raise RuntimeError("FIREWORKS_BASE_URL is required for Fireworks execution")
        return OpenAICompatibleProvider(base_url, api_key)
    if name == "llama-cpp":
        return LlamaCppProvider()
    raise ValueError(f"unknown provider override: {name}")


def validate_output(expected_format: str, text: str) -> dict[str, Any]:
    if not text.strip():
        return {"passed": False, "reason": "empty_output"}
    if expected_format == "json":
        try:
            json.loads(text)
        except json.JSONDecodeError:
            return {"passed": False, "reason": "invalid_json"}
    return {"passed": True, "reason": "ok"}


def structural_repair(expected_format: str, text: str) -> tuple[str, dict[str, Any]]:
    validation = validate_output(expected_format, text)
    if validation["passed"] or expected_format != "json":
        return text, {"attempted": False, "reason": validation["reason"]}
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        repaired = validate_output(expected_format, candidate)
        if repaired["passed"]:
            return candidate, {"attempted": True, "reason": "extracted_json_object"}
    return text, {"attempted": True, "reason": "structural_repair_unavailable"}


def run_task(
    task: Task,
    provider_override: str | None = None,
    allowed_models: list[str] | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    task_family = normalize_task_family(task.task_family, task.prompt)
    jurisdiction = jurisdiction_for(task_family, provider_override)
    packet = compile_execution_packet(task, task_family, jurisdiction)
    decision = route_task(task_family, jurisdiction, provider_override, allowed_models)
    initial_decision = decision
    provider = provider_for(decision.provider)
    fallback_reason = None
    allow_policy_fallback = provider_override in {"version5", VERSION_6_PRODUCTION_PROVIDER, VERSION_6_STAGING_PROVIDER}
    try:
        result = provider.complete(packet["compiled_prompt"], decision.model)
    except RuntimeError as exc:
        if (
            not allow_policy_fallback
            or decision.candidate_version not in {"version_5", "version_6"}
            or decision.provider not in (VERSION_5_LOCAL_PROVIDERS | {VERSION_6_LOCAL_PROVIDER})
        ):
            raise
        fallback_reason = f"local_runtime_failure: {exc}"
        fallback_provider = VERSION_6_STAGING_PROVIDER if provider_override == VERSION_6_STAGING_PROVIDER else "fireworks"
        decision = route_task(task_family, jurisdiction, fallback_provider, allowed_models)
        provider = provider_for(decision.provider)
        result = provider.complete(packet["compiled_prompt"], decision.model)
    output, repair = structural_repair(packet["answer_schema"]["format"], result.text)
    validation = validate_output(packet["answer_schema"]["format"], output)
    if (
        decision.candidate_version in {"version_5", "version_6"}
        and decision.provider in (VERSION_5_LOCAL_PROVIDERS | {VERSION_6_LOCAL_PROVIDER})
        and not validation["passed"]
        and allow_policy_fallback
    ):
        fallback_reason = f"local_validation_failure: {validation['reason']}"
        fallback_provider = VERSION_6_STAGING_PROVIDER if provider_override == VERSION_6_STAGING_PROVIDER else "fireworks"
        decision = route_task(task_family, jurisdiction, fallback_provider, allowed_models)
        provider = provider_for(decision.provider)
        result = provider.complete(packet["compiled_prompt"], decision.model)
        output, repair = structural_repair(packet["answer_schema"]["format"], result.text)
        validation = validate_output(packet["answer_schema"]["format"], output)

    candidate_version = initial_decision.candidate_version
    local_certification = initial_decision.local_certification
    selected_path = "local_then_fireworks_fallback" if fallback_reason else initial_decision.selected_path
    local_attempted = candidate_version in {"version_5", "version_6"} and initial_decision.provider in (
        VERSION_5_LOCAL_PROVIDERS | {VERSION_6_LOCAL_PROVIDER}
    )
    local_success = bool(local_attempted and not fallback_reason and validation["passed"])
    fireworks_used = decision.provider == "fireworks"
    retry_count = 1 if fallback_reason else 0
    staging_remote_used = decision.provider == VERSION_6_STAGING_PROVIDER
    if fireworks_used:
        fireworks_token_usage: dict[str, Any] = {
            "prompt_tokens": result.token_usage.get("prompt_tokens", 0),
            "completion_tokens": result.token_usage.get("completion_tokens", 0),
            "total_tokens": result.token_usage.get("total_tokens", 0),
        }
        judged_fireworks_tokens: int | str = int(fireworks_token_usage["total_tokens"])
    elif staging_remote_used:
        fireworks_token_usage = {"judged_fireworks_tokens": "not_applicable", "official_fireworks_token_score": "NOT_MEASURED"}
        judged_fireworks_tokens = "not_applicable"
    else:
        fireworks_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        judged_fireworks_tokens = 0

    record = {
        **packet,
        "candidate_version": candidate_version,
        "selected_provider": decision.provider,
        "selected_path": selected_path,
        "selected_model": decision.model,
        "allowed_models_source": "ALLOWED_MODELS" if decision.provider == "fireworks" else "not_required_for_provider",
        "local_certification": local_certification,
        "local_attempted": local_attempted,
        "local_success": local_success,
        "local_failure": fallback_reason if local_attempted and fallback_reason else None,
        "fallback_reason": fallback_reason,
        "routing_reason": initial_decision.reason,
        "routing_policy": initial_decision.policy,
        "final_mode_compliant": decision.final_mode_compliant,
        "validation_result": validation,
        "repair": repair,
        "token_usage": result.token_usage,
        "fireworks_token_usage": fireworks_token_usage,
        "judged_fireworks_tokens": judged_fireworks_tokens,
        "official_fireworks_token_score": "NOT_MEASURED" if staging_remote_used else judged_fireworks_tokens,
        "retry_count": retry_count,
        "memory_estimate": None,
        "latency": {"milliseconds": result.latency_ms},
        "output": output,
    }

    destination = run_dir or Path(os.environ.get("APP_RUN_DIR", ROOT / "runs"))
    destination.mkdir(parents=True, exist_ok=True)
    out_path = destination / f"{task.id}-{int(time.time())}.json"
    write_json(out_path, record)
    record["record_path"] = str(out_path)
    return record


def run_scenario(
    scenario_id: str,
    profile_id: str = "version-3-work-jurisdiction",
    provider_override: str | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    _ = profile_id
    scenario = load_scenarios()[scenario_id]
    return run_task(scenario_to_task(scenario), provider_override=provider_override, run_dir=run_dir)


def run_tasks_file(
    input_path: Path = Path("/input/tasks.json"),
    output_path: Path = Path("/output/results.json"),
    provider_override: str | None = None,
) -> dict[str, Any]:
    allowed_models = parse_allowed_models()
    batch_run_dir = Path(os.environ.get("APP_RUN_DIR", str(output_path.parent / "runs")))
    records = [
        run_task(task, provider_override=provider_override, allowed_models=allowed_models, run_dir=batch_run_dir)
        for task in load_submission_tasks(input_path)
    ]
    official_results = [{"task_id": record["task_id"], "answer": record["output"]} for record in records]
    write_json(output_path, official_results)
    return {
        "schema": "amd_hackathon.submission_run.v1",
        "mode": submission_mode_name(provider_override),
        "result_path": str(output_path),
        "task_count": len(records),
        "results": official_results,
        "audit_records": records,
    }


def preflight() -> dict[str, Any]:
    allowed_models = parse_allowed_models()
    policy_status: dict[str, Any] = {}
    for provider_name in sorted(VERSION_6_POLICY_REQUIRED_PROVIDERS):
        try:
            policy = load_version6_policy(provider_name)
            policy_status[provider_name] = {
                "compact_policy_present": True,
                "policy_schema_valid": True,
                "policy_mode_matches_image": True,
                "policy_id": policy["policy_id"],
                "policy_mode": policy["policy_mode"],
                "provider_boundary": policy["provider_boundary"],
            }
        except RuntimeError as exc:
            policy_status[provider_name] = {
                "compact_policy_present": False,
                "policy_schema_valid": False,
                "policy_mode_matches_image": False,
                "error": str(exc),
            }
    return {
        "repo_root": str(ROOT),
        "doctrine": "version-6-confirmed-submission-runtime",
        "version_6": VERSION_6_MODE,
        "version_6_submission_providers": sorted(VERSION_6_PROVIDERS),
        "version_6_staging_remote_baseline_provider": VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
        "version_6_policy_status": policy_status,
        "version_5_candidate_available": False,
        "version_5_local_model_status": "ollama_runtime_certified_jurisdictions_pending_benchmark_promotion",
        "version_5_local_model": VERSION_5_LOCAL_MODEL,
        "version_5_runtime_certification": VERSION_5_RUNTIME_CERTIFICATION,
        "version_5_local_certified_count": sum(
            1 for row in VERSION_5_LOCAL_CERTIFICATION.values() if row["local_status"] == "LOCAL_CERTIFIED"
        ),
        "llama_cpp_binary": os.environ.get("LLAMA_CPP_BINARY", "/app/bin/llama-cli"),
        "llama_model_path": os.environ.get("LLAMA_MODEL_PATH", VERSION_5_LOCAL_MODEL["image_path"]),
        "llama_context_length": int(os.environ.get("LLAMA_CONTEXT_LENGTH", "2048")),
        "llama_threads": int(os.environ.get("LLAMA_THREADS", "2")),
        "version5_ollama_provider": VERSION_5_LOCAL_PROVIDER,
        "version6_ollama_provider": VERSION_6_LOCAL_PROVIDER,
        "version6_production_provider": VERSION_6_PRODUCTION_PROVIDER,
        "version6_staging_provider": VERSION_6_STAGING_PROVIDER,
        "staging_remote_provider": os.environ.get("STAGING_REMOTE_PROVIDER"),
        "staging_remote_provider_required": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
        "staging_allowed_models_count": len(parse_staging_allowed_models()),
        "staging_inference_model": os.environ.get("STAGING_INFERENCE_MODEL"),
        "ollama_cloud_base_url": os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://ollama.com"),
        "ollama_cloud_api_key_configured": bool(os.environ.get("OLLAMA_API_KEY")),
        "ollama_cloud_model_mappings": OLLAMA_CLOUD_MODEL_MAPPINGS,
        "ollama_cloud_not_for_submission": True,
        "version5_ollama_model": os.environ.get("OLLAMA_MODEL_NAME", VERSION_5_LOCAL_MODEL["model_name"]),
        "version5_ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
        "version5_ollama_context_length": int(os.environ.get("OLLAMA_CONTEXT_LENGTH", "128")),
        "version5_ollama_max_loaded_models": int(os.environ.get("OLLAMA_MAX_LOADED_MODELS", "1")),
        "version5_ollama_num_parallel": int(os.environ.get("OLLAMA_NUM_PARALLEL", "1")),
        "fireworks_base_url_configured": bool(os.environ.get("FIREWORKS_BASE_URL")),
        "fireworks_api_key_configured": bool(os.environ.get("FIREWORKS_API_KEY")),
        "allowed_models_count": len(allowed_models),
        "allowed_models_source": "ALLOWED_MODELS",
        "ollama_demo_model": os.environ.get("MODEL_NAME", "qwen2.5-coder:3b"),
        "ollama_demo_only": True,
        "lemonade_active_runtime": False,
    }


def submission_mode_name(provider_override: str | None) -> str:
    if provider_override == VERSION_6_PRODUCTION_PROVIDER:
        return "version_6_production_submission"
    if provider_override == VERSION_6_STAGING_PROVIDER:
        return "version_6_staging_submission_shape"
    if provider_override == VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER:
        return "version_6_staging_remote_baseline"
    if provider_override == VERSION_6_LOCAL_PROVIDER:
        return "version_6_direct_ollama_evidence"
    if provider_override == "ollama-demo":
        return "version_3_demo"
    if provider_override == "version5":
        return "version_5_candidate"
    if provider_override == VERSION_5_LOCAL_PROVIDER:
        return "version_5_direct_ollama_benchmark"
    if provider_override == "llama-cpp":
        return "version_5_direct_llama_cpp_benchmark"
    return "fireworks_final_compatible"


def record_to_json(record: dict[str, Any]) -> str:
    return json.dumps(record, indent=2, sort_keys=True)
