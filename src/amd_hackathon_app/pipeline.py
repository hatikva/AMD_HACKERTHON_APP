from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Scenario:
    id: str
    task_family: str
    prompt: str
    expected_format: str
    difficulty_hint: int
    evidence_refs: list[str]


@dataclass(frozen=True)
class Difficulty:
    estimate: int
    confidence: float


@dataclass(frozen=True)
class RouteDecision:
    provider: str
    model: str
    reason: str
    escalate: bool


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


def load_scenarios(path: Path = ROOT / "benchmarks/scenarios.json") -> dict[str, Scenario]:
    rows = load_json(path)
    return {row["id"]: Scenario(**row) for row in rows}


def load_profile(profile_id: str) -> dict[str, Any]:
    return load_json(ROOT / f"configs/profiles/{profile_id}.json")


def classify(scenario: Scenario) -> str:
    return scenario.task_family


def estimate_difficulty(scenario: Scenario) -> Difficulty:
    confidence = 0.9 if scenario.difficulty_hint <= 2 else 0.82
    return Difficulty(estimate=scenario.difficulty_hint, confidence=confidence)


def retrieve_context(scenario: Scenario, max_refs: int) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for ref in scenario.evidence_refs[:max_refs]:
        path = ROOT / ref
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        refs.append({"ref": ref, "content": content})
    return refs


def compile_context_packet(
    scenario: Scenario,
    profile: dict[str, Any],
    difficulty: Difficulty,
) -> dict[str, Any]:
    refs = retrieve_context(scenario, profile["mdr_budget"]["max_refs"])
    evidence_text = "\n\n".join(f"[{row['ref']}]\n{row['content']}" for row in refs)
    compiled_prompt = (
        "Use the evidence and task contract. Preserve accuracy over cost.\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        f"Task:\n{scenario.prompt}\n\n"
        f"Expected format: {scenario.expected_format}"
    )
    return {
        "task_id": scenario.id,
        "profile_id": profile["profile_id"],
        "task_family": scenario.task_family,
        "difficulty_estimate": difficulty.estimate,
        "router_confidence": difficulty.confidence,
        "retrieval_query": scenario.prompt,
        "selected_memory_refs": [row["ref"] for row in refs],
        "selected_evidence_refs": [row["ref"] for row in refs],
        "omitted_context_reason": "within_budget",
        "compiled_prompt": compiled_prompt,
        "estimated_input_tokens": estimate_tokens(compiled_prompt),
        "provenance": {
            "profile_path": f"configs/profiles/{profile['profile_id']}.json",
            "scenario_path": "benchmarks/scenarios.json",
        },
    }


def route(profile: dict[str, Any], scenario: Scenario, difficulty: Difficulty) -> RouteDecision:
    thresholds = profile["task_thresholds"].get(scenario.task_family, {})
    max_local = int(thresholds.get("max_local_difficulty", 1))
    min_confidence = float(thresholds.get("min_router_confidence", 0.8))
    api_model = os.environ.get(profile.get("api_model_env", "FIREWORKS_MODEL"), "configured-fireworks-model")

    if difficulty.estimate > max_local:
        return RouteDecision("fireworks", api_model, "difficulty_above_local_threshold", True)
    if difficulty.confidence < min_confidence:
        return RouteDecision("fireworks", api_model, "router_confidence_below_threshold", True)
    return RouteDecision("local", profile["local_model"], "within_local_threshold", False)


class MockProvider:
    name = "mock"

    def complete(self, prompt: str, model: str) -> ProviderResult:
        start = time.perf_counter()
        if "Extract JSON" in prompt:
            text = '{"name":"Hatikva","track":"AMD Hackathon Track 1"}'
        elif "Classify" in prompt:
            text = "docs"
        else:
            text = "Escalate ambiguous high-difficulty tasks unless validation evidence shows local reliability."
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


def provider_for(name: str) -> Any:
    if name == "mock":
        return MockProvider()
    if name == "local":
        return OpenAICompatibleProvider(os.environ.get("LEMONADE_BASE_URL", "http://127.0.0.1:13305/api/v1"))
    if name == "fireworks":
        api_key = os.environ.get("FIREWORKS_API_KEY")
        if not api_key:
            raise RuntimeError("FIREWORKS_API_KEY is required for Fireworks execution")
        return OpenAICompatibleProvider(os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"), api_key)
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


def run_scenario(
    scenario_id: str,
    profile_id: str = "balanced-local-first",
    provider_override: str | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    scenario = load_scenarios()[scenario_id]
    profile = load_profile(profile_id)
    difficulty = estimate_difficulty(scenario)
    packet = compile_context_packet(scenario, profile, difficulty)
    decision = route(profile, scenario, difficulty)

    provider_name = provider_override or decision.provider
    provider = provider_for(provider_name)
    if provider_name == "mock":
        model = "mock-model"
    elif provider_override == "local":
        model = profile["local_model"]
    elif provider_override == "fireworks":
        model = os.environ.get(profile.get("api_model_env", "FIREWORKS_MODEL"), decision.model)
    else:
        model = decision.model
    result = provider.complete(packet["compiled_prompt"], model)
    validation = validate_output(scenario.expected_format, result.text)

    record = {
        **packet,
        "selected_provider": provider_name,
        "selected_model": model,
        "fallback_or_escalation_reason": decision.reason,
        "validation_result": validation,
        "token_usage": result.token_usage,
        "latency": {"milliseconds": result.latency_ms},
        "output": result.text,
    }

    destination = run_dir or Path(os.environ.get("APP_RUN_DIR", ROOT / "runs"))
    destination.mkdir(parents=True, exist_ok=True)
    out_path = destination / f"{scenario.id}-{int(time.time())}.json"
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record["record_path"] = str(out_path)
    return record


def preflight() -> dict[str, Any]:
    return {
        "repo_root": str(ROOT),
        "lemonade_base_url": os.environ.get("LEMONADE_BASE_URL", "http://127.0.0.1:13305/api/v1"),
        "fireworks_configured": bool(os.environ.get("FIREWORKS_API_KEY")),
        "routing_profile": os.environ.get("ROUTING_PROFILE", "balanced-local-first"),
    }


def record_to_json(record: dict[str, Any]) -> str:
    return json.dumps(record, indent=2, sort_keys=True)
