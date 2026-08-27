"""Tests for the D-006 UI data/rendering layer (without Streamlit)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.schemas import ResearchReport
from app.ui.components import (
    claim_markdown,
    experiment_status_message,
    formal_claims,
    formal_risks,
    metric_rows,
    non_formal_claims,
)
from app.ui.data import (
    DEFAULT_REPORT_PATH,
    build_ui_model,
    load_report,
    load_ui_model,
    report_export_payloads,
)
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


def test_load_ui_model_reads_complete_artifact_bundle(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(REPORT_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    markdown_path = tmp_path / "report.md"
    markdown_path.write_text("# 原始报告\n\n仅用于导出测试。\n", encoding="utf-8")
    metadata_path = tmp_path / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
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
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "status": "success",
                "metrics": {"key_factor_coverage_rate": 0.75},
            }
        ),
        encoding="utf-8",
    )

    model = load_ui_model(
        report_path,
        metadata_path=metadata_path,
        metrics_path=metrics_path,
        report_markdown_path=markdown_path,
    )

    assert model["report"]["company_name"] == "合成测试公司"
    assert model["report_markdown"] == "# 原始报告\n\n仅用于导出测试。\n"
    assert model["run_metadata"]["status"] == "success"
    assert model["metrics"]["metrics"]["key_factor_coverage_rate"] == 0.75
    assert model["file_status"]["report.json"]["status"] == "loaded"
    assert model["file_status"]["report.md"]["status"] == "loaded"


def test_load_ui_model_keeps_metadata_when_report_is_missing(tmp_path: Path) -> None:
    metadata_path = tmp_path / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "run_id": "RUN-FAILED",
                "started_at": "2026-08-20T00:00:00Z",
                "finished_at": "2026-08-20T00:01:00Z",
                "status": "failed",
                "model_provider": "rule-engine",
                "model_name": "test",
                "prompt_versions": {},
                "input_hashes": {},
                "module_versions": {},
                "errors": ["E500 report generation failed"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    model = load_ui_model(
        tmp_path / "missing-report.json",
        metadata_path=metadata_path,
    )

    assert model["report"] is None
    assert model["run_metadata"]["status"] == "failed"
    assert model["run_metadata"]["errors"] == ["E500 report generation failed"]
    assert model["file_status"]["report.json"]["status"] == "missing"
    assert "report.json" in model["missing_files"]


def test_load_ui_model_preserves_failed_and_disabled_result_rows(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            [
                {
                    "experiment_id": "E1",
                    "name": "generic_agent",
                    "status": "disabled",
                    "metrics": None,
                    "error": "disabled until mode switch",
                },
                {
                    "experiment_id": "E2",
                    "name": "industry_agent",
                    "status": "failed",
                    "metrics": None,
                    "error": "E500 report generation failed",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    model = load_ui_model(REPORT_FIXTURE, results_path=results_path)

    assert [row["status"] for row in model["experiment_rows"]] == [
        "disabled",
        "failed",
    ]
    assert "已禁用" in experiment_status_message(model["experiment_rows"][0])
    assert "失败" in experiment_status_message(model["experiment_rows"][1])


def test_load_ui_model_reads_csv_results_without_recomputing_metrics(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.csv"
    results_path.write_text(
        "experiment_id,name,case_id,status,key_factor_coverage_rate,error\n"
        "E0,manual_baseline,food_main,success,0.75,\n"
        "E1,generic_agent,food_main,disabled,,disabled\n",
        encoding="utf-8",
    )

    model = load_ui_model(REPORT_FIXTURE, results_path=results_path)

    assert model["file_status"]["results"]["status"] == "loaded"
    assert model["experiment_rows"][0]["metrics"]["key_factor_coverage_rate"] == "0.75"
    assert model["experiment_rows"][1]["status"] == "disabled"


def test_load_ui_model_surfaces_invalid_optional_metrics_file(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text("{not-json", encoding="utf-8")

    model = load_ui_model(REPORT_FIXTURE, metrics_path=metrics_path)

    assert model["metrics"] is None
    assert model["file_status"]["metrics.json"]["status"] == "invalid"
    assert any("metrics.json" in message for message in model["errors"])


def test_load_ui_model_infers_markdown_and_metadata_from_run_layout(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "outputs" / "reports" / "RUN-DEMO" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(REPORT_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    report_path.with_name("report.md").write_text("# RUN-DEMO\n", encoding="utf-8")
    metadata_path = tmp_path / "outputs" / "logs" / "RUN-DEMO" / "run_metadata.json"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(
        json.dumps(
            {
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
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    model = load_ui_model(report_path)

    assert model["report"]["run_id"] == "RUN-SYN-METRICS"
    assert model["report_markdown"]
    assert model["run_metadata"]["status"] == "success"
    assert model["file_status"]["report.md"]["status"] == "loaded"
    assert model["file_status"]["run_metadata.json"]["status"] == "loaded"


def test_report_export_payloads_preserve_read_only_artifacts(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_text = REPORT_FIXTURE.read_text(encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    markdown_text = "# 导出报告\n"
    markdown_path = tmp_path / "report.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    model = load_ui_model(report_path, report_markdown_path=markdown_path)
    exports = report_export_payloads(model)

    assert exports["report.json"] == report_text
    assert exports["report.md"] == markdown_text
    assert report_path.read_text(encoding="utf-8") == report_text
    assert markdown_path.read_text(encoding="utf-8") == markdown_text


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
    before = json.dumps(report, ensure_ascii=False, sort_keys=True)
    claim = report["claims"][0]

    markdown = claim_evidence_markdown(claim, report)

    assert "EV-SYN-REV" in markdown
    assert "营业收入同比增长" in markdown
    assert "事实" in markdown
    assert "页码" in markdown
    assert json.dumps(report, ensure_ascii=False, sort_keys=True) == before


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


def test_default_report_path_is_committed_fixture() -> None:
    assert DEFAULT_REPORT_PATH.exists()
    assert "fixtures" in DEFAULT_REPORT_PATH.parts
    assert "outputs" not in DEFAULT_REPORT_PATH.parts


def test_streamlit_script_imports_ui_package_from_repo_root() -> None:
    script = ROOT / "app" / "ui" / "app.py"
    code = (
        "import runpy, sys; "
        f"sys.path.insert(0, {str(script.parent)!r}); "
        f"sys.path.insert(1, {str(ROOT)!r}); "
        f"runpy.run_path({str(script)!r}, run_name='not_main')"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_formal_claims_only_include_pass_claims() -> None:
    report = load_report(REPORT_FIXTURE).model_dump(mode="json")
    report["claims"].append(
        {
            "claim_id": "CL-REVIEW",
            "text": "待确认结论",
            "claim_type": "analysis",
            "risk_severity": None,
            "evidence_ids": ["EV-SYN-REV"],
            "calculation": None,
            "confidence": 0.5,
            "industry_metric_ids": ["revenue_growth"],
            "status": "review",
        }
    )

    formal = formal_claims(report)
    non_formal = non_formal_claims(report)

    assert all(claim["status"] == "pass" for claim in formal)
    assert all(claim["status"] != "pass" for claim in non_formal)
    assert any(claim["claim_id"] == "CL-REVIEW" for claim in non_formal)


def test_formal_risks_only_include_pass_risks() -> None:
    report = load_report(REPORT_FIXTURE).model_dump(mode="json")
    report["risks"] = [
        {
            "claim_id": "CL-RISK-PASS",
            "text": "正式风险",
            "claim_type": "risk",
            "risk_severity": "high",
            "evidence_ids": ["EV-SYN-REV"],
            "calculation": None,
            "confidence": 0.7,
            "industry_metric_ids": ["food_safety"],
            "status": "pass",
        },
        {
            "claim_id": "CL-RISK-REVIEW",
            "text": "待确认风险",
            "claim_type": "risk",
            "risk_severity": "medium",
            "evidence_ids": ["EV-SYN-REV"],
            "calculation": None,
            "confidence": 0.5,
            "industry_metric_ids": ["food_safety"],
            "status": "review",
        },
    ]

    formal = formal_risks(report)

    assert [risk["claim_id"] for risk in formal] == ["CL-RISK-PASS"]
