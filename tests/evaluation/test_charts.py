"""Tests for D-005 chart generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.charts import generate_charts


def _write_results(path: Path) -> Path:
    rows = [
        {
            "experiment_id": "E0",
            "name": "manual_baseline",
            "case_id": "food_main",
            "status": "success",
            "started_at": "2026-08-27T09:00:00+08:00",
            "finished_at": "2026-08-27T09:30:00+08:00",
            "error_count": 0,
            "validation_issue_count": 1,
            "metrics": {
                "key_factor_coverage_rate": 0.8,
                "evidence_validity_rate": 0.9,
                "cutoff_violation_count": 0,
                "industry_metric_coverage_rate": 1.0,
            },
        },
        {
            "experiment_id": "E1",
            "name": "generic_agent",
            "case_id": "food_main",
            "status": "disabled",
            "metrics": None,
        },
        {
            "experiment_id": "E2",
            "name": "industry_agent",
            "case_id": "food_main",
            "status": "failed",
            "metrics": None,
            "error": "boom",
        },
        {
            "experiment_id": "E3",
            "name": "full_system",
            "case_id": "food_main",
            "status": "success",
            "error_count": 0,
            "validation_issue_count": 2,
            "metrics": {
                "key_factor_coverage_rate": 0.6,
                "evidence_validity_rate": 0.7,
                "cutoff_violation_count": 1,
                "industry_metric_coverage_rate": 0.8,
            },
        },
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def test_generate_charts_writes_five_svg_files(tmp_path: Path) -> None:
    results = _write_results(tmp_path / "results.json")
    out = tmp_path / "charts"

    written = generate_charts(results, out)

    assert len(written) == 5
    expected = {
        "coverage.svg",
        "evidence_validity.svg",
        "errors_and_cutoff.svg",
        "manual_time.svg",
        "bank_migration_coverage.svg",
    }
    assert {path.name for path in written} == expected
    for path in written:
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("<svg")


def test_disabled_rows_are_not_plotted_as_zero(tmp_path: Path) -> None:
    results = _write_results(tmp_path / "results.json")
    out = tmp_path / "charts"

    generate_charts(results, out)

    coverage = (out / "coverage.svg").read_text(encoding="utf-8")
    # E1 disabled 不应出现为 0 的柱子；应只有 E0/E3 两个 bar 标签。
    assert coverage.count("<rect") == 2
    assert "E1" not in coverage


def test_bank_missing_data_renders_no_data_not_zero(tmp_path: Path) -> None:
    results = _write_results(tmp_path / "results.json")
    out = tmp_path / "charts"

    generate_charts(results, out)

    bank = (out / "bank_migration_coverage.svg").read_text(encoding="utf-8")
    assert "no data" in bank
    assert "0.00" not in bank


def test_errors_chart_includes_cutoff_failure_and_validation_counts(
    tmp_path: Path,
) -> None:
    results = _write_results(tmp_path / "results.json")
    out = tmp_path / "charts"

    generate_charts(results, out)

    errors = (out / "errors_and_cutoff.svg").read_text(encoding="utf-8")
    assert "cutoff 违规" in errors
    assert "失败运行" in errors
    assert "ValidationIssue" in errors
    assert "E2" in errors


def test_missing_results_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="results file does not exist"):
        generate_charts(tmp_path / "missing.json", tmp_path / "out")


def test_empty_results_generates_no_data_charts(tmp_path: Path) -> None:
    results = tmp_path / "results.json"
    results.write_text("[]", encoding="utf-8")
    out = tmp_path / "charts"

    generate_charts(results, out)

    content = (out / "coverage.svg").read_text(encoding="utf-8")
    assert "no data" in content
