"""Tests for the D-006 UI data/rendering layer (without Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas import ResearchReport
from app.ui.components import claim_markdown, metric_rows
from app.ui.data import build_ui_model, load_report
from app.ui.evidence_view import claim_evidence_markdown, evidence_by_id, format_evidence


ROOT = Path(__file__).resolve().parents[2]
REPORT_FIXTURE = ROOT / "fixtures" / "evaluation" / "report_sample.json"
RUN_DEMO_REPORT = ROOT / "outputs" / "reports" / "RUN-DEMO" / "report.json"
RUN_DEMO_METADATA = ROOT / "outputs" / "logs" / "RUN-DEMO" / "run_metadata.json"


def test_load_report_validates_research_report() -> None:
    report = load_report(REPORT_FIXTURE)

    assert isinstance(report, ResearchReport)
    assert report.run_id == "RUN-SYN-METRICS"


def test_build_ui_model_loads_report_without_extra_files() -> None:
    model = build_ui_model(REPORT_FIXTURE)

    assert model["report"]["company_name"] == "合成测试公司"
    assert model["run_metadata"] is None
    assert model["metrics"] is None


def test_build_ui_model_loads_optional_metadata(tmp_path: Path) -> None:
    metadata = {
        "run_id": "RUN-SYN-METRICS",
        "started_at": "2026-08-20T00:00:00Z",
        "finished_at": "2026-08-20T00:01:00Z",
        "status": "success",
        "model_provider": "manual",
        "model_name": "human",
        "prompt_versions": {},
        "input_hashes": {},
        "module_versions": {},
        "errors": [],
    }
    metadata_path = tmp_path / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    model = build_ui_model(REPORT_FIXTURE, metadata_path=metadata_path)

    assert model["run_metadata"]["status"] == "success"


def test_missing_report_raises_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="file does not exist"):
        build_ui_model(tmp_path / "missing.json")


def test_evidence_by_id_and_format_evidence() -> None:
    report = load_report(REPORT_FIXTURE).model_dump(mode="json")
    evidence = evidence_by_id(report, "EV-SYN-REV")

    assert evidence is not None
    text = format_evidence(evidence)
    assert "EV-SYN-REV" in text
    assert "DOC-SYN-001" in text


def test_claim_evidence_markdown_includes_attached_evidence() -> None:
    report = load_report(REPORT_FIXTURE).model_dump(mode="json")
    claim = report["claims"][0]

    markdown = claim_evidence_markdown(claim, report)

    assert "EV-SYN-REV" in markdown
    assert "营业收入同比增长" in markdown


def test_metric_rows_are_stable_and_labeled() -> None:
    rows = metric_rows(
        {
            "key_factor_coverage_rate": 0.5,
            "evidence_validity_rate": 0.333333,
            "cutoff_violation_count": 1.0,
        }
    )

    assert rows[0][0] == "关键因素覆盖率"
    assert rows[0][1] == "0.5"
    assert any(label == "Cutoff 违规次数" for label, _ in rows)


def test_claim_markdown_includes_id_status_and_text() -> None:
    report = load_report(REPORT_FIXTURE).model_dump(mode="json")
    claim = report["claims"][0]

    markdown = claim_markdown(claim)

    assert claim["claim_id"] in markdown
    assert claim["status"] in markdown
    assert claim["text"] in markdown
