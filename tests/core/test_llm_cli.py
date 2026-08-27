"""Tests for the CLI --llm entry point (ADAPT-008) and --mode switch."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import scripts.run_case as run_case
from app.model import JsonFileCache, ModelProviderError
from app.schemas import ResearchReport


ROOT = Path(__file__).parents[2]


def test_run_case_llm_flag_constructs_provider(monkeypatch) -> None:
    captured: dict[str, object] = {}
    report = ResearchReport(
        run_id="RUN-DEMO",
        company_name="示例食品公司",
        industry_id="food_beverage",
        cutoff_date=date(2026, 8, 20),
        summary=[],
        claims=[],
        risks=[],
        unresolved_items=[],
        evidence_index=[],
        validation_issues=[],
        generated_at=datetime.now(timezone.utc),
        report_version="test",
    )

    def fake_run_research(request, *, model_provider=None, mode="rule-engine"):
        del request
        captured["model_provider"] = model_provider
        captured["mode"] = mode
        return report

    monkeypatch.setattr(run_case, "run_research", fake_run_research)

    request_fixture = ROOT / "fixtures" / "shared" / "research_request.json"
    exit_code = run_case.main(["--request", str(request_fixture), "--llm"])

    assert exit_code == 0
    assert captured["model_provider"] is not None
    assert isinstance(captured["model_provider"].cache, JsonFileCache)
    assert captured["model_provider"].cache.path.name == "model_cache.json"
    assert captured["mode"] == "rule-engine"


def test_run_case_llm_preserves_e300_in_stderr(monkeypatch, capsys) -> None:
    request_fixture = ROOT / "fixtures" / "shared" / "research_request.json"

    def fake_run_research(request, *, model_provider=None, mode="rule-engine"):
        del request, model_provider, mode
        raise ModelProviderError(
            "E300 module=model.transport: test failure"
        )

    monkeypatch.setattr(run_case, "run_research", fake_run_research)

    exit_code = run_case.main(["--request", str(request_fixture), "--llm"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "E300 module=model.transport" in captured.err
    assert "file=" in captured.err
    assert "Check FINCOUNCIL_MODEL_*" in captured.err
    assert "E500" not in captured.err


def test_run_case_llm_preserves_e301_in_stderr(monkeypatch, capsys) -> None:
    request_fixture = ROOT / "fixtures" / "shared" / "research_request.json"

    def fake_run_research(request, *, model_provider=None, mode="rule-engine"):
        del request, model_provider, mode
        raise ModelProviderError(
            "E301 module=model.transport: response missing chat content"
        )

    monkeypatch.setattr(run_case, "run_research", fake_run_research)

    exit_code = run_case.main(["--request", str(request_fixture), "--llm"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "E301 module=model.transport" in captured.err
    assert "file=" in captured.err
    assert "Check FINCOUNCIL_MODEL_*" in captured.err
    assert "E500" not in captured.err


def test_run_case_experiment_mode_requires_llm(monkeypatch) -> None:
    def fake_run_research(request, *, model_provider=None, mode="rule-engine"):
        del request, model_provider, mode
        raise AssertionError("experiment mode without --llm must not call run_research")

    monkeypatch.setattr(run_case, "run_research", fake_run_research)
    request_fixture = ROOT / "fixtures" / "shared" / "research_request.json"
    exit_code = run_case.main(["--request", str(request_fixture), "--mode", "E1"])

    assert exit_code == 2


def test_run_case_mode_passed_to_run_research(monkeypatch) -> None:
    captured: dict[str, object] = {}
    report = ResearchReport(
        run_id="RUN-DEMO",
        company_name="示例食品公司",
        industry_id="food_beverage",
        cutoff_date=date(2026, 8, 20),
        summary=[],
        claims=[],
        risks=[],
        unresolved_items=[],
        evidence_index=[],
        validation_issues=[],
        generated_at=datetime.now(timezone.utc),
        report_version="test",
    )

    def fake_run_research(request, *, model_provider=None, mode="rule-engine"):
        del request, model_provider
        captured["mode"] = mode
        return report

    monkeypatch.setattr(run_case, "run_research", fake_run_research)

    request_fixture = ROOT / "fixtures" / "shared" / "research_request.json"
    exit_code = run_case.main(
        ["--request", str(request_fixture), "--llm", "--mode", "E2"]
    )

    assert exit_code == 0
    assert captured["mode"] == "E2"
