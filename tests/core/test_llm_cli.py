"""Tests for the CLI --llm entry point (ADAPT-008)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import scripts.run_case as run_case
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

    def fake_run_research(request, *, model_provider=None):
        del request
        captured["model_provider"] = model_provider
        return report

    monkeypatch.setattr(run_case, "run_research", fake_run_research)

    request_fixture = ROOT / "fixtures" / "shared" / "research_request.json"
    exit_code = run_case.main(["--request", str(request_fixture), "--llm"])

    assert exit_code == 0
    assert captured["model_provider"] is not None
