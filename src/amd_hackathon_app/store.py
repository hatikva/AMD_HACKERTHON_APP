from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def db_path() -> Path:
    return Path(os.environ.get("APP_DB_PATH", ROOT / "data" / "app.sqlite3"))


def connect(path: Path | None = None) -> sqlite3.Connection:
    destination = path or db_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(destination)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        create table if not exists runs (
          id integer primary key autoincrement,
          created_at integer not null,
          suite_id text,
          scenario_id text not null,
          profile_id text not null,
          provider text not null,
          model text not null,
          validation_passed integer not null,
          total_tokens integer not null,
          latency_ms integer not null,
          record_json text not null
        )
        """
    )
    migrate_runs(conn)
    conn.commit()
    return conn


def migrate_runs(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("pragma table_info(runs)").fetchall()}
    columns = {
        "run_type": "text",
        "local_provider": "text",
        "local_model": "text",
        "remote_provider": "text",
        "remote_model": "text",
        "route_side": "text",
        "routing_reason": "text",
    }
    for column, definition in columns.items():
        if column not in existing:
            conn.execute(f"alter table runs add column {column} {definition}")


def save_run(record: dict[str, Any], suite_id: str | None = None, path: Path | None = None) -> int:
    conn = connect(path)
    with conn:
        cursor = conn.execute(
            """
            insert into runs (
              created_at, suite_id, scenario_id, profile_id, provider, model,
              validation_passed, total_tokens, latency_ms, record_json,
              run_type, local_provider, local_model, remote_provider, remote_model,
              route_side, routing_reason
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                suite_id,
                str(record["task_id"]),
                str(record["profile_id"]),
                str(record["selected_provider"]),
                str(record["selected_model"]),
                1 if record.get("validation_result", {}).get("passed") else 0,
                int(record.get("token_usage", {}).get("total_tokens", 0)),
                int(record.get("latency", {}).get("milliseconds", 0)),
                json.dumps(record, sort_keys=True),
                str(record.get("run_type", "")),
                str(record.get("local_provider", "")),
                str(record.get("local_model", "")),
                str(record.get("remote_provider", "")),
                str(record.get("remote_model", "")),
                str(record.get("selected_route_side", "")),
                str(record.get("fallback_or_escalation_reason", "")),
            ),
        )
        return int(cursor.lastrowid)


def list_runs(limit: int = 100, path: Path | None = None) -> list[dict[str, Any]]:
    conn = connect(path)
    rows = conn.execute(
        """
        select id, created_at, suite_id, scenario_id, profile_id, provider, model,
               validation_passed, total_tokens, latency_ms, run_type,
               local_provider, local_model, remote_provider, remote_model,
               route_side, routing_reason
        from runs
        order by id desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_run(run_id: int, path: Path | None = None) -> dict[str, Any] | None:
    conn = connect(path)
    row = conn.execute("select record_json from runs where id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return json.loads(str(row["record_json"]))
