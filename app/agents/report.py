"""Formal report renderer for the research pipeline.

The report agent never adds new facts: it only partitions already validated
Claims into report sections and formats them into the shared ``ResearchReport``
schema or Markdown text.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import (
    Claim,
    Evidence,
    InvestmentDecisionSupport,
    NarrativeBlock,
    NarrativeSegment,
    ResearchReport,
    ResearchRequest,
    ValidationIssue,
)


_REPORTABLE_STATUSES = {"pass", "review"}
_BODY_CLAIM_TYPES = {"fact", "change", "analysis"}
_BLOCKING_SEVERITIES = {"error", "critical"}


def _is_reportable(claim: Claim) -> bool:
    """A claim enters the report only when it is pass or review.

    Rejected and draft Claims are intentionally excluded; ``draft`` Claims are
    also flagged by the Critic as unparsed model output.
    """

    return claim.status in _REPORTABLE_STATUSES


def _blocking_claim_ids(issues: list[ValidationIssue]) -> set[str]:
    return {
        issue.claim_id
        for issue in issues
        if issue.status == "open"
        and issue.severity in _BLOCKING_SEVERITIES
        and issue.claim_id is not None
    }


def _blocking_evidence_ids(issues: list[ValidationIssue]) -> set[str]:
    return {
        issue.evidence_id
        for issue in issues
        if issue.status == "open"
        and issue.severity in _BLOCKING_SEVERITIES
        and issue.evidence_id is not None
    }


def _apply_issue_gating(
    claims: list[Claim],
    issues: list[ValidationIssue],
) -> list[Claim]:
    """Downgrade pass Claims that are blocked by open error/critical issues.

    The Critic reports problems without mutating Claim status, so the report
    renderer must apply those issues when deciding what may enter the body.
    ``error``/``critical`` issues targeting a Claim ID or one of its evidence
    IDs demote the Claim from ``pass`` to ``review``.
    """

    blocked_claim_ids = _blocking_claim_ids(issues)
    blocked_evidence_ids = _blocking_evidence_ids(issues)
    gated: list[Claim] = []
    for claim in claims:
        if not _is_reportable(claim):
            continue
        is_blocked = (
            claim.claim_id in blocked_claim_ids
            or any(evidence_id in blocked_evidence_ids for evidence_id in claim.evidence_ids)
        )
        if is_blocked and claim.status == "pass":
            claim = claim.model_copy(update={"status": "review"})
        gated.append(claim)
    return gated


def _build_summary(
    *,
    body_count: int,
    risk_count: int,
    review_count: int,
    unresolved_count: int,
    evidence_count: int,
) -> list[str]:
    """Build a metadata-only summary without inventing facts."""

    return [
        f"生成 {body_count} 条正文结论、{risk_count} 条风险。",
        f"另有 {review_count} 条待人工确认、{unresolved_count} 个未决项。",
        f"证据索引共 {evidence_count} 条。",
    ]


def _build_narrative(reportable: list[Claim]) -> list[NarrativeBlock]:
    """Project reportable claims into a readable, evidence-bound narrative.

    Each Claim is intentionally kept as one sentence-level segment. This avoids
    guessing which source supports a sentence after prose has been concatenated.
    A later LLM synthesis pass may replace these blocks with finer segmentation,
    but it must preserve the same explicit Evidence IDs.
    """

    body_segments = [
        NarrativeSegment(
            segment_id=f"SEG-{claim.claim_id.removeprefix('CL-')}",
            text=claim.text,
            evidence_ids=claim.evidence_ids,
            claim_type=claim.claim_type,
            status=claim.status,
        )
        for claim in reportable
        if claim.claim_type in _BODY_CLAIM_TYPES and claim.status == "pass"
    ]
    risk_segments = [
        NarrativeSegment(
            segment_id=f"SEG-{claim.claim_id.removeprefix('CL-')}",
            text=claim.text,
            evidence_ids=claim.evidence_ids,
            claim_type=claim.claim_type,
            status=claim.status,
        )
        for claim in reportable
        if claim.claim_type == "risk" and claim.status == "pass"
    ]

    blocks: list[NarrativeBlock] = []
    if body_segments:
        blocks.append(NarrativeBlock(section="核心判断", segments=body_segments))
    if risk_segments:
        blocks.append(NarrativeBlock(section="风险与待确认", segments=risk_segments))
    return blocks


def _build_empty_narrative() -> list[NarrativeBlock]:
    return [
        NarrativeBlock(
            section="研究状态",
            segments=[
                NarrativeSegment(
                    segment_id="SEG-EMPTY-REPORT",
                    text="本次运行暂未形成可单独发布的结论，请结合证据索引和质量检查进行人工复核。",
                    evidence_ids=[],
                    claim_type="unresolved",
                    status="review",
                )
            ],
        )
    ]


def render_report(
    request: ResearchRequest,
    claims: list[Claim],
    evidence: list[Evidence],
    issues: list[ValidationIssue],
    *,
    narrative: list[NarrativeBlock] | None = None,
) -> ResearchReport:
    """Build a structured ``ResearchReport`` from validated Claims.

    Only ``pass`` and ``review`` Claims are kept. ``reject`` Claims are dropped
    from the report, and ``draft`` Claims are not reportable either. Open
    ``error``/``critical`` Critic issues demote affected ``pass`` Claims to
    ``review`` so they cannot appear in the body. Review Claims remain in the
    ``claims``/``risks`` lists with ``status="review"`` so downstream UI and
    Markdown can place them in the pending-confirmation section without losing
    them. The evidence index only contains verified Evidence actually
    referenced by reportable Claims.
    """

    reportable = _apply_issue_gating(claims, issues)
    narrative = narrative if narrative is not None else _build_narrative(reportable)
    if not narrative and evidence:
        narrative = _build_empty_narrative()

    body_claims = [
        claim
        for claim in reportable
        if claim.claim_type in _BODY_CLAIM_TYPES
    ]
    risks = [
        claim
        for claim in reportable
        if claim.claim_type == "risk"
    ]
    unresolved_items = [
        claim
        for claim in reportable
        if claim.claim_type == "unresolved"
    ]
    pass_body_count = sum(1 for claim in body_claims if claim.status == "pass")
    pass_risk_count = sum(1 for claim in risks if claim.status == "pass")
    review_count = sum(
        1
        for claim in [*body_claims, *risks]
        if claim.status == "review"
    )

    referenced_evidence_ids = {
        evidence_id
        for claim in reportable
        for evidence_id in claim.evidence_ids
    }
    referenced_evidence_ids.update(
        evidence_id
        for block in narrative
        for segment in block.segments
        for evidence_id in segment.evidence_ids
    )
    if not referenced_evidence_ids:
        referenced_evidence_ids = {
            item.evidence_id for item in evidence if item.review_status == "verified"
        }
    evidence_index = sorted(
        (
            item
            for item in evidence
            if item.evidence_id in referenced_evidence_ids
            and item.review_status == "verified"
        ),
        key=lambda item: item.evidence_id,
    )
    investment_view = _build_investment_view(body_claims, risks, evidence_index)

    return ResearchReport(
        run_id=request.run_id,
        company_name=request.company_name,
        industry_id=request.industry_id,
        cutoff_date=request.cutoff_date,
        summary=_build_summary(
            body_count=pass_body_count,
            risk_count=pass_risk_count,
            review_count=review_count,
            unresolved_count=len(unresolved_items),
            evidence_count=len(evidence_index),
        ),
        narrative=narrative,
        investment_view=investment_view,
        claims=body_claims,
        risks=risks,
        unresolved_items=unresolved_items,
        evidence_index=evidence_index,
        validation_issues=issues,
        generated_at=datetime.now(timezone.utc),
        report_version="v1-a008",
    )


def _build_investment_view(
    claims: list[Claim],
    risks: list[Claim],
    evidence: list[Evidence],
) -> InvestmentDecisionSupport:
    """Build a conservative action frame without inventing valuation facts."""

    pass_claims = [claim for claim in claims if claim.status == "pass"]
    pass_risks = [claim for claim in risks if claim.status == "pass"]
    if not pass_claims:
        stance = "当前证据不足"
    elif len(pass_risks) > len(pass_claims):
        stance = "中性观察"
    else:
        stance = "值得深入跟踪"
    return InvestmentDecisionSupport(
        stance=stance,
        horizon="中长期，需结合估值与组合约束复核",
        thesis=[claim.text for claim in pass_claims[:4]],
        catalysts=[],
        risks=[claim.text for claim in pass_risks[:4]],
        entry_conditions=[
            "补齐当前价格、估值倍数和同行比较数据",
            "核心经营指标继续改善，并由截止日前正式来源核验",
        ],
        invalidation_conditions=[
            "核心盈利或经营现金流出现持续恶化",
            "新增高严重度风险且无法被后续证据排除",
        ],
        data_gaps=[
            "实时及历史价格",
            "PE、PB、自由现金流收益率等估值指标",
            "同行公司可比数据与行业周期位置",
        ],
        valuation_status="not_available",
        confidence=min(1.0, len(evidence) / 20) if evidence else 0.0,
    )


def _format_claim_line(claim: Claim) -> str:
    evidence = "、".join(claim.evidence_ids) if claim.evidence_ids else "无"
    severity = (
        f"，风险等级 {claim.risk_severity}"
        if claim.risk_severity is not None
        else ""
    )
    return (
        f"- {claim.text} "
        f"（{claim.claim_id}，置信度 {claim.confidence}{severity}，证据：{evidence}）"
    )


def render_markdown(report: ResearchReport) -> str:
    """Render a ResearchReport as Markdown without adding facts."""

    lines: list[str] = [
        f"# 投研简报：{report.company_name}",
        "",
        f"- run_id：{report.run_id}",
        f"- 行业：{report.industry_id}",
        f"- cutoff_date：{report.cutoff_date.isoformat()}",
        f"- 生成时间：{report.generated_at.isoformat()}",
        f"- 报告版本：{report.report_version}",
        "",
        "## 摘要",
    ]
    lines.extend(f"- {item}" for item in report.summary)
    lines.append("")

    if report.investment_view is not None:
        view = report.investment_view
        lines.extend([
            "## 投资决策支持",
            "",
            f"- 当前立场：{view.stance}",
            f"- 研究期限：{view.horizon}",
            f"- 估值状态：{'已接入' if view.valuation_status == 'available' else '尚未接入'}",
            f"- 证据充分度：{view.confidence:.2f}",
            "",
            "### 核心依据",
        ])
        lines.extend(f"- {item}" for item in view.thesis or ["暂无通过校验的核心依据。"])
        lines.extend(["", "### 进入条件"])
        lines.extend(f"- {item}" for item in view.entry_conditions)
        lines.extend(["", "### 失效条件"])
        lines.extend(f"- {item}" for item in view.invalidation_conditions)
        lines.extend(["", "### 数据缺口"])
        lines.extend(f"- {item}" for item in view.data_gaps)
        lines.append("")

    lines.append("## 投研正文")
    if report.narrative:
        for block in report.narrative:
            lines.append(f"### {block.section}")
            for segment in block.segments:
                evidence = "、".join(segment.evidence_ids) if segment.evidence_ids else "待确认"
                lines.append(f"- {segment.text}（证据：{evidence}）")
            lines.append("")
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 正文结论")
    pass_claims = [claim for claim in report.claims if claim.status == "pass"]
    if pass_claims:
        lines.extend(_format_claim_line(claim) for claim in pass_claims)
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 风险")
    pass_risks = [claim for claim in report.risks if claim.status == "pass"]
    if pass_risks:
        lines.extend(_format_claim_line(claim) for claim in pass_risks)
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 待人工确认")
    pending = [
        claim
        for claim in [*report.claims, *report.risks]
        if claim.status == "review"
    ]
    if pending:
        lines.extend(_format_claim_line(claim) for claim in pending)
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 未决项")
    if report.unresolved_items:
        lines.extend(_format_claim_line(claim) for claim in report.unresolved_items)
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 证据索引")
    if report.evidence_index:
        for item in report.evidence_index:
            lines.append(
                f"- {item.evidence_id}：{item.fact_text}（定位：{item.locator}）"
            )
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 校验问题")
    if report.validation_issues:
        for issue in report.validation_issues:
            lines.append(f"- [{issue.severity}] {issue.message}")
    else:
        lines.append("- 无。")

    return "\n".join(lines) + "\n"
