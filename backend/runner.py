"""Single-concurrency background research runner.

The runner intentionally keeps only one active research task at a time. It is
a thin adapter over ``app.main.run_research`` and never re-implements analysis,
evidence, Critic, or report logic.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.main import run_research
from app.model import (
    JsonFileCache,
    ModelProvider,
    create_openai_compatible_transport,
)

from backend.cases import build_workbench_request
from backend.config import Settings
from backend.db import RunStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchRunner:
    """Start and track one background research task at a time."""

    def __init__(self, store: RunStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings
        self._lock = threading.Lock()
        self._active = False

    def is_busy(self) -> bool:
        with self._lock:
            return self._active

    def start(
        self,
        *,
        run_id: str,
        case_id: str,
        cutoff_date: Any,
    ) -> bool:
        """Start a background task if no task is currently running."""
        with self._lock:
            if self._active:
                return False
            self._active = True

        thread = threading.Thread(
            target=self._execute,
            args=(run_id, case_id, cutoff_date),
            name=f"research-{run_id}",
            daemon=True,
        )
        thread.start()
        return True

    def _execute(
        self,
        run_id: str,
        case_id: str,
        cutoff_date: Any,
    ) -> None:
        try:
            self._store.update_run(
                run_id,
                status="running",
                started_at=_now_iso(),
                stage="准备研究请求",
            )

            request = build_workbench_request(
                case_id,
                cutoff_date,
                run_id,
                outputs_dir=self._settings.outputs_dir,
            )

            if not self._settings.llm_available():
                raise ValueError("E300 module=workbench.runner: research model is unavailable")
            cache_path = self._settings.outputs_dir / "cache" / "model_cache.json"
            provider = ModelProvider.from_env(
                transport=create_openai_compatible_transport(),
                cache=JsonFileCache(cache_path),
            )

            def on_progress(stage: str) -> None:
                self._store.append_progress(run_id, stage)

            run_research(
                request,
                model_provider=provider,
                progress_callback=on_progress,
            )

            report_dir = self._settings.outputs_dir / "reports" / run_id
            report_path = report_dir / "report.json"
            markdown_path = report_dir / "report.md"
            metadata_path = (
                self._settings.outputs_dir / "logs" / run_id / "run_metadata.json"
            )
            self._store.update_run(
                run_id,
                status="success",
                finished_at=_now_iso(),
                report_path=str(report_path),
                markdown_path=str(markdown_path),
                metadata_path=str(metadata_path),
                stage="研究完成",
            )
        except Exception as exc:  # noqa: BLE001 - persisted as structured failure
            self._store.update_run(
                run_id,
                status="failed",
                finished_at=_now_iso(),
                error=str(exc),
                stage="失败",
            )
        finally:
            with self._lock:
                self._active = False
