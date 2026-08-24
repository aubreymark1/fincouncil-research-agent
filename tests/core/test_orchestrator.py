"""Tests for the A-003 minimum orchestrator and CLI-facing entry point."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import run_research
from app.schemas import ResearchReport, ResearchRequest, RunMetadata


ROOT = Path(__file__).parents[2]
REQUEST_FIXTURE = ROOT / "fixtures" / "shared" / "research_request.json"


def test_run_research_writes_valid_report_and_metadata(tmp_path: Path) -> None:
    payload = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
    payload["output_dir"] = str(tmp_path / "outputs" / "reports" / "RUN-DEMO")
    request = ResearchRequest.model_validate(payload)

    report = run_research(request)

    report_path = Path(request.output_dir) / "report.json"
    metadata_path = tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json"
    saved_report = ResearchReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    saved_metadata = RunMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))

    assert report == saved_report
    assert saved_report.run_id == "RUN-DEMO"
    assert saved_report.claims[0].status == "pass"
    assert saved_report.claims[0].evidence_ids == ["EV-FOOD-001"]
    assert saved_metadata.status == "success"
    assert saved_metadata.model_name == "a003-stub"
