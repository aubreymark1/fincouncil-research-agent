"""SQLite persistence for workbench run state.

The schema is intentionally small: run metadata, status, progress, and artifact
paths. No credentials or environment values are stored.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    """Thread-safe SQLite store for workbench runs."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.RLock()

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    llm_enabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    report_path TEXT,
                    markdown_path TEXT,
                    metadata_path TEXT,
                    stage TEXT,
                    progress_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)"
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        data["llm_enabled"] = bool(data["llm_enabled"])
        try:
            data["progress"] = json.loads(data.pop("progress_json") or "[]")
        except json.JSONDecodeError:
            data["progress"] = []
        return data

    def create_run(
        self,
        *,
        run_id: str,
        case_id: str,
        mode: str = "rule-engine",
        llm_enabled: bool = False,
    ) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, case_id, status, mode, llm_enabled, created_at,
                    started_at, finished_at, error, report_path, markdown_path,
                    metadata_path, stage, progress_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    case_id,
                    "queued",
                    mode,
                    1 if llm_enabled else 0,
                    _now_iso(),
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "[]",
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return self._row_to_dict(row)  # type: ignore[return-value]

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status",
            "started_at",
            "finished_at",
            "error",
            "report_path",
            "markdown_path",
            "metadata_path",
            "stage",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return self.get_run(run_id)

        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = [updates[key] for key in updates] + [run_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE runs SET {assignments} WHERE run_id = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return self._row_to_dict(row)  # type: ignore[return-value]

    def append_progress(self, run_id: str, stage: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT progress_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            try:
                progress = json.loads(row["progress_json"] or "[]")
            except json.JSONDecodeError:
                progress = []
            if not isinstance(progress, list):
                progress = []
            progress.append(stage)
            conn.execute(
                "UPDATE runs SET progress_json = ?, stage = ? WHERE run_id = ?",
                (json.dumps(progress, ensure_ascii=False), stage, run_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return self._row_to_dict(updated)  # type: ignore[return-value]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return self._row_to_dict(row)

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._row_to_dict(row) for row in rows if row is not None]
