"""Tests for workbench runner fallback behaviour."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.model import ModelProviderError
from backend.config import Settings
from backend.db import RunStore
from backend.runner import ResearchRunner


def make_runner(tmp_path: Path) -> tuple[ResearchRunner, RunStore, Settings]:
    settings = Settings(
        project_root=Path(__file__).resolve().parents[2],
        outputs_dir=tmp_path / "outputs",
        db_path=tmp_path / "data" / "workbench.db",
        enable_llm_demo=True,
        max_runs_per_ip_per_minute=10,
    )
    store = RunStore(settings.db_path)
    store.init()
    return ResearchRunner(store, settings), store, settings


def wait_for_runner(runner: ResearchRunner) -> None:
    for _ in range(200):
        if not runner.is_busy():
            return
        time.sleep(0.01)
    pytest.fail("runner did not finish")


def test_llm_failure_falls_back_to_rule_engine(monkeypatch, tmp_path: Path) -> None:
    for name, value in {
        "FINCOUNCIL_ENABLE_LLM_DEMO": "true",
        "FINCOUNCIL_MODEL_PROVIDER": "fixture",
        "FINCOUNCIL_MODEL_NAME": "fixture-model",
        "FINCOUNCIL_MODEL_BASE_URL": "https://example.invalid",
        "FINCOUNCIL_MODEL_API_KEY": "fixture-key",
    }.items():
        monkeypatch.setenv(name, value)
    calls: list[tuple[bool, str]] = []

    def fake_run_research(request, *, model_provider, llm_strategy, progress_callback):
        del request
        calls.append((model_provider is not None, llm_strategy))
        if model_provider is not None:
            raise ModelProviderError("E301 module=agents.compact: invalid output")
        progress_callback("写入报告产物")

    monkeypatch.setattr("backend.runner.run_research", fake_run_research)
    runner, store, _ = make_runner(tmp_path)
    run_id = "RUN-WB-FALLBACK-001"
    store.create_run(run_id=run_id, case_id="food_main", llm_enabled=True)

    assert runner.start(
        run_id=run_id,
        case_id="food_main",
        cutoff_date="2026-08-20",
        llm_enabled=True,
    )
    wait_for_runner(runner)

    row = store.get_run(run_id)
    assert row is not None
    assert row["status"] == "success"
    assert "LLM 增强失败，切换规则引擎" in row["progress"]
    assert calls == [(True, "compact"), (False, "full")]


def test_fallback_failure_is_persisted_as_failed(monkeypatch, tmp_path: Path) -> None:
    for name, value in {
        "FINCOUNCIL_ENABLE_LLM_DEMO": "true",
        "FINCOUNCIL_MODEL_PROVIDER": "fixture",
        "FINCOUNCIL_MODEL_NAME": "fixture-model",
        "FINCOUNCIL_MODEL_BASE_URL": "https://example.invalid",
        "FINCOUNCIL_MODEL_API_KEY": "fixture-key",
    }.items():
        monkeypatch.setenv(name, value)

    def fake_run_research(request, *, model_provider, llm_strategy, progress_callback):
        del request, llm_strategy, progress_callback
        if model_provider is not None:
            raise ModelProviderError("E300 module=agents.compact: transport failed")
        raise RuntimeError("rule engine failed")

    monkeypatch.setattr("backend.runner.run_research", fake_run_research)
    runner, store, _ = make_runner(tmp_path)
    run_id = "RUN-WB-FALLBACK-002"
    store.create_run(run_id=run_id, case_id="food_main", llm_enabled=True)

    assert runner.start(
        run_id=run_id,
        case_id="food_main",
        cutoff_date="2026-08-20",
        llm_enabled=True,
    )
    wait_for_runner(runner)

    row = store.get_run(run_id)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error"] == "rule engine failed"
