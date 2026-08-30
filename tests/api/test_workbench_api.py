"""FastAPI tests for the anonymous workbench backend.

These tests use a fake runner so they never invoke the real research pipeline
or any external model API. The real pipeline is already covered by
``tests/integration``.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db import RunStore
from backend.main import create_app


class FakeRunner:
    """Synchronous fake runner that records starts and writes minimal artifacts."""

    def __init__(self, store: RunStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.busy = False
        self.fail = False
        self.started: list[dict[str, Any]] = []

    def is_busy(self) -> bool:
        return self.busy

    def start(
        self,
        *,
        run_id: str,
        case_id: str,
        cutoff_date: Any,
        llm_enabled: bool = True,
    ) -> bool:
        if self.busy:
            return False
        self.started.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "cutoff_date": cutoff_date,
                "llm_enabled": llm_enabled,
            }
        )
        self.store.update_run(run_id, status="running", started_at=datetime.now(timezone.utc).isoformat())

        if self.fail:
            self.store.update_run(
                run_id,
                status="failed",
                finished_at=datetime.now(timezone.utc).isoformat(),
                error="E500 module=test: simulated failure",
                stage="失败",
            )
            return True

        report_dir = self.settings.outputs_dir / "reports" / run_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "report.json"
        markdown_path = report_dir / "report.md"
        metadata_path = self.settings.outputs_dir / "logs" / run_id / "run_metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "run_id": run_id,
            "company_name": case_id,
            "industry_id": "food_beverage" if case_id == "food_main" else "banking",
            "cutoff_date": str(cutoff_date),
            "summary": ["匿名体验版测试报告。"],
            "claims": [],
            "risks": [],
            "unresolved_items": [],
            "evidence_index": [],
            "validation_issues": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_version": "v1-test",
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(f"# 测试报告 {run_id}\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "mode": "rule-engine",
                    "status": "success",
                    "model_provider": "rule-engine",
                    "model_name": "a008-rules",
                    "prompt_versions": {},
                    "input_hashes": {},
                    "module_versions": {},
                    "errors": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        self.store.update_run(
            run_id,
            status="success",
            finished_at=datetime.now(timezone.utc).isoformat(),
            report_path=str(report_path),
            markdown_path=str(markdown_path),
            metadata_path=str(metadata_path),
            stage="研究完成",
        )
        return True


@pytest.fixture()
def app_env(tmp_path: Path):
    static_dir = tmp_path / "frontend"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<html><body>FinCouncil test shell</body></html>", encoding="utf-8")
    settings = Settings(
        project_root=Path(__file__).resolve().parents[2],
        outputs_dir=tmp_path / "outputs",
        db_path=tmp_path / "data" / "workbench.db",
        enable_llm_demo=False,
        llm_available_override=True,
        max_runs_per_ip_per_minute=100,
        static_dir=static_dir,
    )
    store = RunStore(settings.db_path)
    store.init()
    runner = FakeRunner(store, settings)
    app = create_app(settings, runner)
    return TestClient(app), store, runner, settings


@pytest.fixture()
def unavailable_app_env(tmp_path: Path):
    settings = Settings(
        project_root=Path(__file__).resolve().parents[2],
        outputs_dir=tmp_path / "outputs",
        db_path=tmp_path / "data" / "workbench.db",
        enable_llm_demo=False,
        llm_available_override=False,
        max_runs_per_ip_per_minute=100,
    )
    store = RunStore(settings.db_path)
    store.init()
    runner = FakeRunner(store, settings)
    return TestClient(create_app(settings, runner)), store, runner, settings


def test_root_serves_frontend_shell(app_env):
    client, _, _, _ = app_env
    response = client.get("/")
    assert response.status_code == 200
    assert "FinCouncil test shell" in response.text


def test_health(app_env):
    client, _, _, _ = app_env
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "fincouncil-anonymous-workbench"
    assert body["llm_available"] is True


def test_cases_returns_only_verified_packages(app_env):
    client, _, _, _ = app_env
    response = client.get("/api/cases")
    assert response.status_code == 200
    cases = response.json()
    assert [case["case_id"] for case in cases] == ["food_main", "bank_main"]
    assert all(case["supports_llm"] for case in cases)


def test_create_food_main_task(app_env):
    client, _, runner, _ = app_env
    response = client.post(
        "/api/runs",
        json={"case_id": "food_main", "cutoff_date": "2026-08-20"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["run_id"].startswith("RUN-WB-")
    assert body["case_id"] == "food_main"
    assert body["mode"] == "rule-engine"
    assert body["status"] == "success"
    assert body["report_ready"] is True
    assert runner.started[0]["llm_enabled"] is True


def test_llm_toggle_is_rejected_and_new_runs_are_llm_only(app_env):
    client, _, runner, _ = app_env
    rejected = client.post(
        "/api/runs",
        json={
            "case_id": "food_main",
            "cutoff_date": "2026-08-20",
            "llm_enabled": False,
        },
    )
    assert rejected.status_code == 422

    created = client.post(
        "/api/runs",
        json={"case_id": "food_main", "cutoff_date": "2026-08-20"},
    )
    assert created.status_code == 202
    assert runner.started[0]["llm_enabled"] is True


def test_create_bank_main_task(app_env):
    client, _, runner, _ = app_env
    response = client.post(
        "/api/runs",
        json={"case_id": "bank_main", "cutoff_date": "2026-08-20"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["case_id"] == "bank_main"
    assert runner.started[0]["case_id"] == "bank_main"


def test_unknown_case_is_rejected(app_env):
    client, _, _, _ = app_env
    response = client.post(
        "/api/runs",
        json={"case_id": "unknown_company", "cutoff_date": "2026-08-20"},
    )
    assert response.status_code == 404
    assert "only supports food_main and bank_main" in response.json()["detail"]


def test_model_unavailable_is_rejected(unavailable_app_env):
    client, _, _, _ = unavailable_app_env
    response = client.post(
        "/api/runs",
        json={"case_id": "food_main", "cutoff_date": "2026-08-20"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "研究模型暂不可用，请稍后重试。"


def test_single_concurrency_rejects_second_run(app_env):
    client, _, runner, _ = app_env
    runner.busy = True
    response = client.post(
        "/api/runs",
        json={"case_id": "food_main", "cutoff_date": "2026-08-20"},
    )
    assert response.status_code == 409
    assert "正在运行" in response.json()["detail"]


def test_failed_task_status_and_report_error(app_env):
    client, _, runner, _ = app_env
    runner.fail = True
    response = client.post(
        "/api/runs",
        json={"case_id": "food_main", "cutoff_date": "2026-08-20"},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    status = client.get(f"/api/runs/{run_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "failed"
    assert "simulated failure" in status.json()["error"]

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 409


def test_report_and_downloads(app_env):
    client, _, _, _ = app_env
    create = client.post(
        "/api/runs",
        json={"case_id": "bank_main", "cutoff_date": "2026-08-20"},
    )
    run_id = create.json()["run_id"]

    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 200
    assert report.json()["run_id"] == run_id

    metadata = client.get(f"/api/runs/{run_id}/metadata")
    assert metadata.status_code == 200
    assert metadata.json()["status"] == "success"

    json_download = client.get(f"/api/runs/{run_id}/download/report.json")
    assert json_download.status_code == 200
    assert json_download.headers["content-type"].startswith("application/json")

    md_download = client.get(f"/api/runs/{run_id}/download/report.md")
    assert md_download.status_code == 200
    assert "text/markdown" in md_download.headers["content-type"]


def test_history_list_returns_created_runs(app_env):
    client, _, _, _ = app_env
    client.post("/api/runs", json={"case_id": "food_main", "cutoff_date": "2026-08-20"})
    client.post("/api/runs", json={"case_id": "bank_main", "cutoff_date": "2026-08-20"})

    response = client.get("/api/runs")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_events_endpoint_supports_resume(app_env):
    client, store, _, _ = app_env
    store.create_run(run_id="RUN-WB-EVENT-API", case_id="food_main", llm_enabled=True)
    store.append_event("RUN-WB-EVENT-API", kind="stage", title="准备研究", summary="完成")
    store.append_event("RUN-WB-EVENT-API", kind="stage", title="定位证据", summary="完成", public_details={"evidence_count": 12})

    response = client.get("/api/runs/RUN-WB-EVENT-API/events?after_sequence=1")
    assert response.status_code == 200
    assert [item["sequence"] for item in response.json()] == [2]


def test_events_stream_returns_sse_records(app_env):
    client, store, _, _ = app_env
    store.create_run(run_id="RUN-WB-EVENT-SSE", case_id="food_main", llm_enabled=True)
    store.append_event("RUN-WB-EVENT-SSE", kind="tool_result", title="检索完成", summary="找到 3 份", status="success")

    response = client.get("/api/runs/RUN-WB-EVENT-SSE/events/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_event" in response.text
    assert '"sequence": 1' in response.text
