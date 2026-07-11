from __future__ import annotations

import json
import os
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .analytics import build_version5_analytics
from .env import load_dotenv
from .pipeline import Task, parse_allowed_models, preflight, run_task, task_from_mapping


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
STATIC_ROOT = ROOT / "web"
UI_RUN_DIR = Path(os.environ.get("UI_RUN_DIR", "/tmp/amd-hackathon-ui-runs"))
GENERATION_LOCK = threading.Lock()

VERSION_PROVIDERS = {
    "version3": "ollama-demo",
    "version4": "fireworks",
    "version5": "version5",
}

VERSION_LABELS = {
    "version3": "Version 3",
    "version4": "Version 4",
    "version5": "Version 5",
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def normalize_versions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["version3"]
    versions = [str(item) for item in value if str(item) in VERSION_PROVIDERS]
    return versions or ["version3"]


def load_tasks_from_payload(payload: dict[str, Any]) -> list[Task]:
    rows = payload.get("tasks", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("tasks must be a non-empty list")
    return [task_from_mapping(row, f"task-{index + 1}") for index, row in enumerate(rows)]


def token_value(record: dict[str, Any], key: str) -> int:
    usage = record.get("token_usage") or {}
    try:
        return int(usage.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def latency_value(record: dict[str, Any]) -> int:
    latency = record.get("latency") or {}
    try:
        return int(latency.get("milliseconds", 0) or 0)
    except (TypeError, ValueError):
        return 0


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [record for record in records if record.get("status") == "completed"]
    blocked = [record for record in records if record.get("status") == "blocked"]
    failed = [record for record in records if record.get("status") == "failed"]
    total_tokens = sum(token_value(record, "total_tokens") for record in completed)
    prompt_tokens = sum(token_value(record, "prompt_tokens") for record in completed)
    completion_tokens = sum(token_value(record, "completion_tokens") for record in completed)
    judged_fireworks_tokens = sum(
        token_value(record, "total_tokens")
        for record in completed
        if record.get("selected_provider") == "fireworks"
    )
    latency_ms = sum(latency_value(record) for record in completed)
    passed = sum(1 for record in completed if (record.get("validation_result") or {}).get("passed") is True)
    providers = sorted({str(record.get("selected_provider")) for record in completed if record.get("selected_provider")})
    models = sorted({str(record.get("selected_model")) for record in completed if record.get("selected_model")})
    return {
        "runs": len(records),
        "completed": len(completed),
        "blocked": len(blocked),
        "failed": len(failed),
        "validation_passed": passed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "judged_fireworks_tokens": judged_fireworks_tokens,
        "local_or_demo_tokens": max(0, total_tokens - judged_fireworks_tokens),
        "latency_ms": latency_ms,
        "avg_latency_ms": int(latency_ms / len(completed)) if completed else 0,
        "providers": providers,
        "models": models,
    }


def blocked_record(version: str, task: Task, error: Exception) -> dict[str, Any]:
    message = str(error)
    status = "blocked" if "required" in message or "not found" in message else "failed"
    return {
        "status": status,
        "candidate_version": version,
        "version_label": VERSION_LABELS[version],
        "task_id": task.id,
        "selected_provider": VERSION_PROVIDERS[version],
        "selected_model": None,
        "work_jurisdiction": None,
        "output": "",
        "validation_result": {"passed": False, "reason": message},
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency": {"milliseconds": 0},
        "error": message,
    }


def run_version_task(version: str, task: Task, allowed_models: list[str]) -> dict[str, Any]:
    provider = VERSION_PROVIDERS[version]
    try:
        if provider == "ollama-demo":
            with GENERATION_LOCK:
                record = run_task(task, provider_override=provider, allowed_models=allowed_models, run_dir=UI_RUN_DIR)
        else:
            record = run_task(task, provider_override=provider, allowed_models=allowed_models, run_dir=UI_RUN_DIR)
    except RuntimeError as exc:
        return blocked_record(version, task, exc)
    except Exception as exc:
        record = blocked_record(version, task, exc)
        record["traceback"] = traceback.format_exc(limit=4)
        return record
    record["status"] = "completed"
    record["candidate_version"] = version
    record["version_label"] = VERSION_LABELS[version]
    return record


def run_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    tasks = load_tasks_from_payload(payload)
    versions = normalize_versions(payload.get("versions"))
    allowed_models = parse_allowed_models()
    records_by_version: dict[str, list[dict[str, Any]]] = {}
    for version in versions:
        records_by_version[version] = [run_version_task(version, task, allowed_models) for task in tasks]
    analytics = {
        version: summarize_records(records)
        for version, records in records_by_version.items()
    }
    return {
        "schema": "amd_hackathon.ui_run.v1",
        "mode": "version_comparison",
        "versions": versions,
        "tasks": [{"id": task.id, "prompt": task.prompt, "task_family": task.task_family, "expected_format": task.expected_format} for task in tasks],
        "analytics": analytics,
        "results": records_by_version,
    }


class UiHandler(BaseHTTPRequestHandler):
    server_version = "AMDHackathonUI/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/preflight":
            self.send_json(preflight())
            return
        if parsed.path == "/api/versions":
            self.send_json({"versions": VERSION_LABELS, "providers": VERSION_PROVIDERS})
            return
        if parsed.path == "/api/version5-analytics":
            self.send_json(build_version5_analytics(ROOT / "qualification/results"))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            self.send_json(run_comparison(payload))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        path = (STATIC_ROOT / relative).resolve()
        if not str(path).startswith(str(STATIC_ROOT.resolve())) or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def run(host: str = "127.0.0.1", port: int = 18083) -> None:
    UI_RUN_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), UiHandler)
    print(f"AMD Hackathon UI listening on http://{host}:{port}")
    server.serve_forever()
