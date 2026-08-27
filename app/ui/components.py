"""Reusable UI components for the D-006 Streamlit page.

Pure helpers return data or Markdown; the Streamlit-specific rendering lives
in ``app.py`` so the helpers can be tested without Streamlit installed.
"""

from __future__ import annotations

from typing import Any

METRIC_LABELS = {
    "key_factor_coverage_rate": "关键因素覆盖率",
    "evidence_validity_rate": "证据有效率",
    "citation_location_accuracy_rate": "引用定位准确率",
    "numeric_error_rate": "数字错误率",
    "cutoff_violation_count": "Cutoff 违规次数",
    "industry_metric_coverage_rate": "行业必查指标覆盖率",
}


def metric_rows(metrics: dict[str, Any]) -> list[tuple[str, str]]:
    """Return a stable list of (label, value) rows for a metrics dict."""
    rows: list[tuple[str, str]] = []
    for key, label in METRIC_LABELS.items():
        if key in metrics:
            rows.append((label, f"{metrics[key]:.4f}".rstrip("0").rstrip(".") if isinstance(metrics[key], float) else str(metrics[key])))
    return rows


def formal_claims(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return pass claims eligible for the formal conclusion section."""
    return [
        claim
        for claim in report.get("claims", [])
        if claim.get("status") == "pass"
    ]


def formal_risks(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return pass risks eligible for the formal risk section."""
    return [
        risk
        for risk in report.get("risks", [])
        if risk.get("status") == "pass"
    ]


def non_formal_claims(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return non-pass claims/risks that should not appear as formal results."""
    return [
        claim
        for claim in [*report.get("claims", []), *report.get("risks", [])]
        if claim.get("status") != "pass"
    ]


def claim_markdown(claim: dict[str, Any]) -> str:
    """Return a compact Markdown representation of one claim."""
    lines = [
        f"- **{claim.get('claim_id', '')}** [{claim.get('status', '')}] "
        f"{claim.get('text', '')}"
    ]
    if claim.get("industry_metric_ids"):
        lines.append(f"  - 指标：{', '.join(claim['industry_metric_ids'])}")
    if claim.get("risk_severity"):
        lines.append(f"  - 风险等级：{claim['risk_severity']}")
    return "\n".join(lines)
