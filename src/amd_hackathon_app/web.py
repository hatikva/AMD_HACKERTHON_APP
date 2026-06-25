from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .env import load_dotenv
from .pipeline import (
    ROOT,
    list_profile_ids,
    load_profile,
    load_scenarios,
    preflight,
    run_benchmark_matrix,
    run_profile_benchmark,
    run_scenario,
    save_profile,
)
from .store import get_run, list_runs


load_dotenv()
STATIC_ROOT = ROOT / "web"


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AMDHackathonApp/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/state":
                scenarios = load_scenarios()
                profiles = {profile_id: load_profile(profile_id) for profile_id in list_profile_ids()}
                json_response(
                    self,
                    {
                        "preflight": preflight(),
                        "scenarios": [scenario.__dict__ for scenario in scenarios.values()],
                        "profiles": profiles,
                        "runs": list_runs(100),
                    },
                )
                return
            if path == "/api/runs":
                limit = int(parse_qs(parsed.query).get("limit", ["100"])[0])
                json_response(self, {"runs": list_runs(limit)})
                return
            if path.startswith("/api/runs/"):
                run_id = int(path.rsplit("/", 1)[1])
                record = get_run(run_id)
                if record is None:
                    json_response(self, {"error": "run not found"}, 404)
                else:
                    json_response(self, record)
                return
            self.serve_static(path)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, 500)

    def do_POST(self) -> None:
        try:
            payload = read_body(self)
            if self.path == "/api/run":
                record = run_scenario(
                    str(payload.get("scenario_id", "classification-basic")),
                    profile_id=str(payload.get("profile_id", "balanced-local-first")),
                    provider_override=str(payload["provider"]) if payload.get("provider") else None,
                    model_override=str(payload["model"]) if payload.get("model") else None,
                    run_type=str(payload.get("run_type", "smoke_test")),
                )
                json_response(self, record)
                return
            if self.path == "/api/demo":
                result = run_profile_benchmark(
                    [str(payload.get("scenario_id", "classification-basic"))],
                    [str(value) for value in payload.get("profile_ids", [])],
                    run_type="demo_run",
                )
                json_response(self, result)
                return
            if self.path == "/api/benchmark":
                providers = [str(value) for value in payload.get("providers", [])]
                models = [str(value) for value in payload.get("models", [])]
                if not providers and not models:
                    result = run_profile_benchmark(
                        [str(value) for value in payload.get("scenario_ids", [])],
                        [str(value) for value in payload.get("profile_ids", [])],
                    )
                    json_response(self, result)
                    return
                result = run_benchmark_matrix(
                    [str(value) for value in payload.get("scenario_ids", [])],
                    [str(value) for value in payload.get("profile_ids", [])],
                    providers,
                    models,
                )
                json_response(self, result)
                return
            if self.path == "/api/profiles":
                profile_id = str(payload["profile_id"])
                profile = payload["profile"]
                if not isinstance(profile, dict):
                    raise ValueError("profile must be an object")
                destination = save_profile(profile_id, profile)
                json_response(self, {"profile_id": profile_id, "path": str(destination)})
                return
            json_response(self, {"error": "not found"}, 404)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, 500)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        target = (STATIC_ROOT / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC_ROOT.resolve())) or not target.exists() or target.is_dir():
            json_response(self, {"error": "not found"}, 404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"AMD Hackathon UI listening on http://{host}:{port}")
    server.serve_forever()
