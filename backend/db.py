"""SQLite persistence for workbench run state.

The schema is intentionally small: run metadata, status, progress, and artifact
paths. No credentials or environment values are stored.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
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
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(runs)").fetchall()
            }
            for column, definition in {
                "source_mode": "TEXT NOT NULL DEFAULT 'verified_case'",
                "subject": "TEXT",
                "ticker": "TEXT",
                "industry_id": "TEXT",
                "research_question": "TEXT",
            }.items():
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    occurred_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    tool_name TEXT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER,
                    source_ids_json TEXT NOT NULL DEFAULT '[]',
                    public_details_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(run_id, sequence),
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_events_run_sequence ON run_events(run_id, sequence)"
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
        source_mode: str = "verified_case",
        subject: str | None = None,
        ticker: str | None = None,
        industry_id: str | None = None,
        research_question: str | None = None,
    ) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, case_id, status, mode, llm_enabled, created_at,
                    started_at, finished_at, error, report_path, markdown_path,
                    metadata_path, stage, progress_json, source_mode, subject,
                    ticker, industry_id, research_question
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    source_mode,
                    subject,
                    ticker,
                    industry_id,
                    research_question,
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

    def append_event(
        self,
        run_id: str,
        *,
        kind: str,
        title: str,
        summary: str,
        tool_name: str | None = None,
        status: str = "running",
        duration_ms: int | None = None,
        source_ids: list[str] | None = None,
        public_details: dict[str, str | int | float | bool] | None = None,
    ) -> dict[str, Any]:
        """Append a redacted event and return its JSON-ready dictionary."""

        from app.schemas.run_event import RunEvent

        details = public_details or {}
        event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            sequence = int(row["next_sequence"] if row is not None else 1)
            event = RunEvent(
                event_id=event_id,
                run_id=run_id,
                sequence=sequence,
                occurred_at=datetime.now(timezone.utc),
                kind=kind,  # type: ignore[arg-type]
                tool_name=tool_name,
                title=title,
                summary=summary,
                status=status,  # type: ignore[arg-type]
                duration_ms=duration_ms,
                source_ids=source_ids or [],
                public_details=details,
            )
            payload = event.model_dump(mode="json")
            conn.execute(
                """
                INSERT INTO run_events (
                    event_id, run_id, sequence, occurred_at, kind, tool_name,
                    title, summary, status, duration_ms, source_ids_json,
                    public_details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["event_id"],
                    payload["run_id"],
                    payload["sequence"],
                    payload["occurred_at"],
                    payload["kind"],
                    payload["tool_name"],
                    payload["title"],
                    payload["summary"],
                    payload["status"],
                    payload["duration_ms"],
                    json.dumps(payload["source_ids"], ensure_ascii=False),
                    json.dumps(payload["public_details"], ensure_ascii=False),
                ),
            )
            conn.commit()
            return payload

    def list_events(self, run_id: str, *, after_sequence: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        from app.schemas.run_event import RunEvent

        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_events WHERE run_id = ? AND sequence > ? ORDER BY sequence ASC LIMIT ?",
                (run_id, after_sequence, limit),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(RunEvent(
                event_id=row["event_id"],
                run_id=row["run_id"],
                sequence=row["sequence"],
                occurred_at=row["occurred_at"],
                kind=row["kind"],
                tool_name=row["tool_name"],
                title=row["title"],
                summary=row["summary"],
                status=row["status"],
                duration_ms=row["duration_ms"],
                source_ids=json.loads(row["source_ids_json"] or "[]"),
                public_details=json.loads(row["public_details_json"] or "{}"),
            ).model_dump(mode="json"))
        return events
