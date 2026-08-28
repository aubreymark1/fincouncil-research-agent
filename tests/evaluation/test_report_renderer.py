"""Tests for D-007 report template rendering."""

from __future__ import annotations

from pathlib import Path

from evaluation.report_renderer import render_report

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "reports" / "template.md.j2"


def _context() -> dict:
    return {
        "title": "食品饮料实验报告",
        "generated_at": "2026-08-27T00:00:00+08:00",
        "experiment_definitions": "evaluation/experiment_definitions.yaml",
        "report": {
            "company_name": "示例食品公司",
            "industry_id": "food_beverage",
            "cutoff_date": "2026-08-20",
            "run_id": "RUN-DEMO",
        },
        "run_metadata": {"status": "success"},
        "metrics": {"key_factor_coverage_rate": 0.8},
        "summary": ["可复现结果已生成"],
        "failures": ["E1 disabled"],
        "manual_review_items": ["待人工确认证据"],
        "rejected_items": ["cutoff 后资料"],
        "bank_migration": "银行 case 待签收",
        "industry_changes": "渠道库存与财务存货口径已拆分",
        "limitations": ["真实 Gold Standard 待签收"],
    }


def test_render_report_contains_expected_sections(tmp_path: Path) -> None:
    rendered = render_report(TEMPLATE, _context())

    assert "# 食品饮料实验报告" in rendered
    assert "## 1. 运行概览" in rendered
    assert "示例食品公司" in rendered
    assert "## 7. 银行迁移复用" in rendered
    assert "真实 Gold Standard 待签收" in rendered


def test_render_report_writes_output_file(tmp_path: Path) -> None:
    output = tmp_path / "report.md"

    rendered = render_report(TEMPLATE, _context(), output)

    assert output.read_text(encoding="utf-8") == rendered
