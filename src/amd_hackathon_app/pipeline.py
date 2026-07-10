from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
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

VERSION_5_LOCAL_CERTIFICATION = {
    "TASK_FAMILY_CLASSIFICATION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_MODEL_ARTIFACT_AND_TESTS_EXIST",
        "validator_coverage": "medium",
    },
    "SHORT_FACTUAL_ANSWERING": {
        "local_status": "FIREWORKS_ONLY",
        "fallback": "FIREWORKS_REQUIRED",
        "validator_coverage": "low",
    },
    "SENTIMENT_CLASSIFICATION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_MODEL_ARTIFACT_AND_TESTS_EXIST",
        "validator_coverage": "high",
    },
    "NAMED_ENTITY_RECOGNITION": {
        "local_status": "LOCAL_DENIED",
        "fallback": "FIREWORKS_ONLY_UNTIL_MODEL_ARTIFACT_AND_TESTS_EXIST",
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


@dataclass(frozen=True)
class ProviderResult:
    text: str
    token_usage: dict[str, int]
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


def load_tasks(path: Path) -> list[Task]:
    payload = load_json(path)
    rows = payload.get("tasks", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("tasks input must be a list or an object with a tasks list")
    return [task_from_mapping(row, f"task-{index + 1}") for index, row in enumerate(rows)]


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
    if provider_override == "version5":
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
        "local_model": os.environ.get("LLAMA_MODEL_NAME", "missing-selected-gguf-model"),
        "local_threshold": None,
        "validator_coverage": row["validator_coverage"],
        "fallback": row["fallback"],
        "fireworks_policy": "ALLOWED_MODELS_ONLY",
        "benchmark_status": "blocked_until_model_artifact_and_tests_exist",
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
    if provider_name == "llama-cpp":
        return os.environ.get("LLAMA_MODEL_PATH", "/app/models/model.gguf")
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
    if provider_name not in {"mock", "fireworks", "ollama-demo", "version5"}:
        raise ValueError(f"unknown provider override: {provider_name}")
    local_certification = None
    candidate_version = "version_3"
    selected_path = provider_name
    if provider_name == "version5":
        candidate_version = "version_5"
        local_certification = local_certification_for(jurisdiction)
        if local_certification["local_status"] == "LOCAL_CERTIFIED":
            provider_name = "llama-cpp"
            selected_path = "local"
        else:
            provider_name = "fireworks"
            selected_path = "fireworks"
    model = select_model(allowed, provider_name)
    final_mode_compliant = provider_name in {"fireworks", "mock", "llama-cpp"}
    if provider_name == "ollama-demo":
        reason = "demo_local_model_execution"
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
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"provider request failed for {self.base_url}: {exc}") from exc

        text = payload["choices"][0]["message"]["content"]
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
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"llama.cpp timed out after {self.timeout_seconds}s") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()[:500]
            raise RuntimeError(f"llama.cpp exited with {completed.returncode}: {stderr}")
        text = completed.stdout.strip()
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
    try:
        result = provider.complete(packet["compiled_prompt"], decision.model)
    except RuntimeError as exc:
        if decision.candidate_version != "version_5" or decision.provider != "llama-cpp":
            raise
        fallback_reason = f"local_runtime_failure: {exc}"
        decision = route_task(task_family, jurisdiction, "fireworks", allowed_models)
        provider = provider_for(decision.provider)
        result = provider.complete(packet["compiled_prompt"], decision.model)
    output, repair = structural_repair(packet["answer_schema"]["format"], result.text)
    validation = validate_output(packet["answer_schema"]["format"], output)
    if (
        decision.candidate_version == "version_5"
        and decision.provider == "llama-cpp"
        and not validation["passed"]
    ):
        fallback_reason = f"local_validation_failure: {validation['reason']}"
        decision = route_task(task_family, jurisdiction, "fireworks", allowed_models)
        provider = provider_for(decision.provider)
        result = provider.complete(packet["compiled_prompt"], decision.model)
        output, repair = structural_repair(packet["answer_schema"]["format"], result.text)
        validation = validate_output(packet["answer_schema"]["format"], output)

    candidate_version = initial_decision.candidate_version
    local_certification = initial_decision.local_certification
    selected_path = "local_then_fireworks_fallback" if fallback_reason else initial_decision.selected_path
    local_attempted = candidate_version == "version_5" and initial_decision.provider == "llama-cpp"
    local_success = bool(local_attempted and not fallback_reason and validation["passed"])
    fireworks_used = decision.provider == "fireworks"
    retry_count = 1 if fallback_reason else 0
    fireworks_token_usage = (
        {
            "prompt_tokens": result.token_usage.get("prompt_tokens", 0),
            "completion_tokens": result.token_usage.get("completion_tokens", 0),
            "total_tokens": result.token_usage.get("total_tokens", 0),
        }
        if fireworks_used
        else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )

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
        "final_mode_compliant": decision.final_mode_compliant,
        "validation_result": validation,
        "repair": repair,
        "token_usage": result.token_usage,
        "fireworks_token_usage": fireworks_token_usage,
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
        for task in load_tasks(input_path)
    ]
    payload = {
        "schema": "amd_hackathon.results.v3",
        "mode": (
            "version_3_demo"
            if provider_override == "ollama-demo"
            else "version_5_candidate"
            if provider_override == "version5"
            else "fireworks_final_compatible"
        ),
        "results": records,
    }
    write_json(output_path, payload)
    return payload


def preflight() -> dict[str, Any]:
    allowed_models = parse_allowed_models()
    return {
        "repo_root": str(ROOT),
        "doctrine": "version-3-most-innovative-routing-system",
        "version_5_candidate_available": True,
        "version_5_local_model_status": "blocked_until_selected_gguf_artifact_is_available",
        "llama_cpp_binary": os.environ.get("LLAMA_CPP_BINARY", "/app/bin/llama-cli"),
        "llama_model_path": os.environ.get("LLAMA_MODEL_PATH", "/app/models/model.gguf"),
        "llama_context_length": int(os.environ.get("LLAMA_CONTEXT_LENGTH", "2048")),
        "llama_threads": int(os.environ.get("LLAMA_THREADS", "2")),
        "fireworks_base_url_configured": bool(os.environ.get("FIREWORKS_BASE_URL")),
        "fireworks_api_key_configured": bool(os.environ.get("FIREWORKS_API_KEY")),
        "allowed_models_count": len(allowed_models),
        "allowed_models_source": "ALLOWED_MODELS",
        "ollama_demo_model": os.environ.get("MODEL_NAME", "qwen2.5-coder:3b"),
        "ollama_demo_only": True,
        "lemonade_active_runtime": False,
    }


def record_to_json(record: dict[str, Any]) -> str:
    return json.dumps(record, indent=2, sort_keys=True)
