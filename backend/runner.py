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
    create_openai_compatible_tool_transport,
)

from backend.cases import build_workbench_request
from backend.config import Settings
from backend.db import RunStore
from app.retrieval.service import RetrievalService
from app.retrieval.tool_registry import build_retrieval_registry
from app.schemas import ResearchRequest, SearchQuery


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
        source_mode: str = "verified_case",
        subject: str | None = None,
        ticker: str | None = None,
        industry_id: str | None = None,
        research_question: str | None = None,
    ) -> bool:
        """Start a background task if no task is currently running."""
        with self._lock:
            if self._active:
                return False
            self._active = True

        thread = threading.Thread(
            target=self._execute,
            args=(run_id, case_id, cutoff_date, source_mode, subject, ticker, industry_id, research_question),
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
        source_mode: str,
        subject: str | None,
        ticker: str | None,
        industry_id: str | None,
        research_question: str | None,
    ) -> None:
        try:
            self._store.update_run(
                run_id,
                status="running",
                started_at=_now_iso(),
                stage="准备研究请求",
            )
            self._store.append_event(
                run_id,
                kind="stage",
                title="准备研究",
                summary="研究任务已启动",
                status="running",
            )

            def on_tool_event(name: str, phase: str, details: dict[str, Any]) -> None:
                if phase == "start":
                    self._store.append_event(
                        run_id,
                        kind="tool_start",
                        title=f"调用工具：{name}",
                        summary="工具开始执行",
                        tool_name=name,
                        status="running",
                    )
                elif phase == "result":
                    self._store.append_event(
                        run_id,
                        kind="tool_result",
                        title=f"工具完成：{name}",
                        summary="工具返回检索结果",
                        tool_name=name,
                        status="success",
                        duration_ms=int(details.get("duration_ms", 0)),
                        public_details={key: value for key, value in details.items() if key in {"count"}},
                    )
                else:
                    self._store.append_event(
                        run_id,
                        kind="error",
                        title=f"工具失败：{name}",
                        summary="工具执行失败",
                        tool_name=name,
                        status="failed",
                        duration_ms=int(details.get("duration_ms", 0)),
                        public_details={"reason": str(details.get("reason", "unknown"))},
                    )

            tool_registry = None
            if source_mode == "verified_case":
                request = build_workbench_request(
                    case_id,
                    cutoff_date,
                    run_id,
                    outputs_dir=self._settings.outputs_dir,
                )
            else:
                if not subject or not research_question:
                    raise ValueError("E500 module=workbench.runner: online research requires subject and question")
                retrieval = RetrievalService(self._settings.outputs_dir)
                query = SearchQuery(
                    subject=subject,
                    ticker=ticker,
                    query=research_question,
                    end_date=cutoff_date,
                )
                manifest_path, _ = retrieval.prepare_manifest(run_id, query)
                tool_registry = build_retrieval_registry(
                    retrieval,
                    subject=subject,
                    ticker=ticker,
                    end_date=cutoff_date,
                    default_query=research_question,
                    event_callback=on_tool_event,
                )
                request = ResearchRequest(
                    run_id=run_id,
                    company_name=subject,
                    ticker=ticker,
                    industry_id=industry_id or "general",
                    research_question=research_question,
                    cutoff_date=cutoff_date,
                    source_manifest_path=str(manifest_path),
                    output_dir=str(self._settings.outputs_dir / "reports" / run_id),
                )

            if not self._settings.llm_available():
                raise ValueError("E300 module=workbench.runner: research model is unavailable")
            cache_path = self._settings.outputs_dir / "cache" / "model_cache.json"
            provider = ModelProvider.from_env(
                transport=create_openai_compatible_transport(),
                tool_transport=create_openai_compatible_tool_transport(),
                cache=JsonFileCache(cache_path),
            )

            def on_progress(stage: str) -> None:
                self._store.append_progress(run_id, stage)
                self._store.append_event(
                    run_id,
                    kind="stage",
                    title=stage,
                    summary=f"已完成：{stage}",
                    status="success",
                )

            run_research(
                request,
                model_provider=provider,
                tool_registry=tool_registry,
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
            self._store.append_event(
                run_id,
                kind="stage",
                title="研究完成",
                summary="报告和证据索引已写入",
                status="success",
            )
        except Exception as exc:  # noqa: BLE001 - persisted as structured failure
            self._store.update_run(
                run_id,
                status="failed",
                finished_at=_now_iso(),
                error=str(exc),
                stage="失败",
            )
            self._store.append_event(
                run_id,
                kind="error",
                title="研究失败",
                summary="研究任务未完成",
                status="failed",
                public_details={"reason": type(exc).__name__},
            )
        finally:
            with self._lock:
                self._active = False
