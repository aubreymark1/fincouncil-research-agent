"""Evidence rendering helpers for the D-006 UI.

These helpers return Markdown/plain-text fragments.  They never modify report
data and never call a model.
"""

from __future__ import annotations

from typing import Any


def format_evidence(evidence: dict[str, Any]) -> str:
    """Format one evidence object as a compact Markdown block."""
    lines = [
        f"- **Evidence**: `{evidence.get('evidence_id', '')}`",
        f"  - 文档：`{evidence.get('doc_id', '')}`",
        f"  - 位置：{evidence.get('locator', '') or '未提供'}",
        f"  - 发布日期：{evidence.get('published_at', '') or '未提供'}",
        f"  - 状态：{evidence.get('review_status', '')}",
    ]
    quote = evidence.get("quote") or evidence.get("fact_text")
    if quote:
        lines.append(f"  - 原文：{quote}")
    return "\n".join(lines)


def evidence_by_id(report: dict[str, Any], evidence_id: str) -> dict[str, Any] | None:
    """Return an evidence object from the report evidence_index by ID."""
    for evidence in report.get("evidence_index", []):
        if evidence.get("evidence_id") == evidence_id:
            return evidence
    return None


def claim_evidence_markdown(claim: dict[str, Any], report: dict[str, Any]) -> str:
    """Return Markdown for all evidence attached to one claim."""
    blocks: list[str] = []
    for evidence_id in claim.get("evidence_ids", []):
        evidence = evidence_by_id(report, evidence_id)
        if evidence is not None:
            blocks.append(format_evidence(evidence))
        else:
            blocks.append(f"- **缺失证据引用**：`{evidence_id}`")
    return "\n".join(blocks)
