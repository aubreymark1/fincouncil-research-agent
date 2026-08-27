"""FastAPI application for the FinCouncil anonymous experience workbench."""

from __future__ import annotations

import json
import threading
import uuid
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.cases import get_workbench_case, list_workbench_cases
from backend.config import Settings
from backend.db import RunStore
from backend.runner import ResearchRunner

APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_available: bool


class CaseInfo(BaseModel):
    case_id: str
    display_name: str
    description: str
    default_cutoff: date
    supports_llm: bool


class CreateRunRequest(BaseModel):
    case_id: str = Field(min_length=1)
    cutoff_date: date
    llm_enabled: bool = False


class RunStatus(BaseModel):
    run_id: str
    case_id: str
    status: Literal["queued", "running", "success", "failed"]
    mode: str
    llm_enabled: bool
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    stage: str | None = None
    progress: list[str] = Field(default_factory=list)
    report_ready: bool = False
    download: dict[str, str] = Field(default_factory=dict)


class RateLimiter:
    """Minimal in-memory per-IP rate limiter for a single-worker process."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        import time

        now = time.monotonic()
        with self._lock:
            queue = self._hits[key]
            while queue and now - queue[0] > self.window_seconds:
                queue.popleft()
            if len(queue) >= self.max_requests:
                return False
            queue.append(now)
            return True


def _row_to_status(row: dict[str, Any]) -> RunStatus:
    run_id = row["run_id"]
    report_ready = bool(row.get("report_path")) and Path(row["report_path"]).exists()
    return RunStatus(
        run_id=run_id,
        case_id=row["case_id"],
        status=row["status"],  # type: ignore[arg-type]
        mode=row["mode"],
        llm_enabled=row["llm_enabled"],
        created_at=datetime.fromisoformat(row["created_at"]),
        started_at=datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None,
        finished_at=datetime.fromisoformat(row["finished_at"]) if row.get("finished_at") else None,
        error=row.get("error"),
        stage=row.get("stage"),
        progress=row.get("progress", []),
        report_ready=report_ready,
        download={
            "report_json": f"/api/runs/{run_id}/download/report.json",
            "report_md": f"/api/runs/{run_id}/download/report.md",
        },
    )


def _read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {p.name}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid JSON file: {p.name}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail=f"JSON root must be an object: {p.name}")
    return payload


def create_app(settings: Settings | None = None, runner: ResearchRunner | None = None) -> FastAPI:
    """Create the FastAPI application.

    ``settings`` and ``runner`` are injectable so API tests can use a temporary
    SQLite database and a fake runner without touching real research work.
    """
    settings = settings or Settings.from_env()
    store = RunStore(settings.db_path)
    store.init()
    runner = runner or ResearchRunner(store, settings)
    limiter = RateLimiter(settings.max_runs_per_ip_per_minute)

    app = FastAPI(
        title="FinCouncil Anonymous Workbench API",
        description="Anonymous experience version of the FinCouncil research workbench.",
        version=APP_VERSION,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="fincouncil-anonymous-workbench",
            version=APP_VERSION,
            llm_available=settings.llm_available(),
        )

    @app.get("/api/cases", response_model=list[CaseInfo])
    def cases() -> list[CaseInfo]:
        return [
            CaseInfo(
                case_id=case.case_id,
                display_name=case.display_name,
                description=case.description,
                default_cutoff=case.default_cutoff,
                supports_llm=case.supports_llm,
            )
            for case in list_workbench_cases()
        ]

    @app.get("/api/runs", response_model=list[RunStatus])
    def list_runs() -> list[RunStatus]:
        rows = store.list_runs(limit=50)
        return [_row_to_status(row) for row in rows]

    @app.post("/api/runs", response_model=RunStatus, status_code=202)
    def create_run(payload: CreateRunRequest, request: Request) -> RunStatus:
        client_ip = request.client.host if request.client else "unknown"
        if not limiter.allow(client_ip):
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试（每 IP 每分钟有运行创建上限）。",
            )

        try:
            case = get_workbench_case(payload.case_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if payload.llm_enabled and not settings.llm_available():
            raise HTTPException(
                status_code=400,
                detail=(
                    "LLM 增强模式未配置。需要 FINCOUNCIL_ENABLE_LLM_DEMO=true "
                    "且 FINCOUNCIL_MODEL_PROVIDER/NAME/BASE_URL/API_KEY 完整；"
                    "请切换回 rule-engine。"
                ),
            )

        if runner.is_busy():
            raise HTTPException(
                status_code=409,
                detail="已有研究任务正在运行，请等待当前任务完成后再试。",
            )

        run_id = f"RUN-WB-{uuid.uuid4().hex[:12].upper()}"
        store.create_run(
            run_id=run_id,
            case_id=case.case_id,
            mode="rule-engine",
            llm_enabled=payload.llm_enabled,
        )

        started = runner.start(
            run_id=run_id,
            case_id=case.case_id,
            cutoff_date=payload.cutoff_date,
            llm_enabled=payload.llm_enabled,
        )
        if not started:
            store.update_run(run_id, status="failed", error="并发冲突：已有任务启动")
            raise HTTPException(
                status_code=409,
                detail="已有研究任务正在运行，请等待当前任务完成后再试。",
            )

        row = store.get_run(run_id)
        if row is None:  # pragma: no cover - defensive invariant
            raise HTTPException(status_code=500, detail="run was not persisted")
        return _row_to_status(row)

    @app.get("/api/runs/{run_id}", response_model=RunStatus)
    def get_run(run_id: str) -> RunStatus:
        row = store.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _row_to_status(row)

    @app.get("/api/runs/{run_id}/report")
    def get_report(run_id: str) -> dict[str, Any]:
        row = store.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        if row["status"] != "success" or not row.get("report_path"):
            raise HTTPException(
                status_code=409,
                detail=row.get("error") or "报告尚未生成",
            )
        return _read_json(row["report_path"])

    @app.get("/api/runs/{run_id}/metadata")
    def get_metadata(run_id: str) -> dict[str, Any]:
        row = store.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        metadata_path = row.get("metadata_path")
        if not metadata_path or not Path(metadata_path).exists():
            raise HTTPException(status_code=404, detail="run metadata not found")
        return _read_json(metadata_path)

    @app.get("/api/runs/{run_id}/download/report.json")
    def download_report_json(run_id: str) -> FileResponse:
        row = store.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        if row["status"] != "success" or not row.get("report_path"):
            raise HTTPException(status_code=409, detail="报告尚未生成")
        path = Path(row["report_path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="report.json not found")
        return FileResponse(
            path,
            media_type="application/json",
            filename=f"{run_id}-report.json",
        )

    @app.get("/api/runs/{run_id}/download/report.md")
    def download_report_md(run_id: str) -> FileResponse:
        row = store.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        if row["status"] != "success" or not row.get("markdown_path"):
            raise HTTPException(status_code=409, detail="报告尚未生成")
        path = Path(row["markdown_path"])
        if not path.exists():
            raise HTTPException(status_code=404, detail="report.md not found")
        return FileResponse(
            path,
            media_type="text/markdown; charset=utf-8",
            filename=f"{run_id}-report.md",
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return app


app = create_app()
