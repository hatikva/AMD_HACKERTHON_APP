from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .analytics import build_version6_analytics
from .env import load_dotenv
from .pipeline import preflight


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
STATIC_ROOT = ROOT / "web"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = records
    fireworks_tokens = sum(int(record.get("judged_fireworks_tokens") or 0) for record in completed)
    return {
        "runs": len(completed),
        "completed": len(completed),
        "judged_fireworks_tokens": fireworks_tokens,
        "providers": sorted({str(record.get("provider")) for record in completed if record.get("provider")}),
        "models": sorted({str(record.get("model")) for record in completed if record.get("model")}),
    }


class UiHandler(BaseHTTPRequestHandler):
    server_version = "AMDVersion6AnalyticsUI/0.1"

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/preflight":
            self.send_json_headers(HTTPStatus.OK, "application/json; charset=utf-8", 0)
            return
        if parsed.path == "/api/version6-analytics":
            self.send_json_headers(HTTPStatus.OK, "application/json; charset=utf-8", 0)
            return
        self.serve_static(parsed.path, include_body=False)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/preflight":
            self.send_json(preflight())
            return
        if parsed.path == "/api/version6-analytics":
            self.send_json(build_version6_analytics(ROOT / "qualification/results"))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        self.send_json(
            {
                "error": "Version 6 analytics UI is read-only and has no task execution endpoint.",
                "submission_runtime": False,
            },
            HTTPStatus.METHOD_NOT_ALLOWED,
        )

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_json_headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def send_json_headers(self, status: HTTPStatus, content_type: str, content_length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_no_store_headers()
        self.end_headers()

    def send_no_store_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def serve_static(self, request_path: str, include_body: bool = True) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        path = (STATIC_ROOT / relative).resolve()
        if not str(path).startswith(str(STATIC_ROOT.resolve())) or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_no_store_headers()
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def run(host: str = "127.0.0.1", port: int = 18084) -> None:
    server = ThreadingHTTPServer((host, port), UiHandler)
    print(f"AMD Version 6 analytics UI listening on http://{host}:{port}")
    server.serve_forever()
