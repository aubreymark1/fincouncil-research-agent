"""Tests for the A-007 formal report renderer."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents import render_markdown, render_report
from app.schemas import Claim, Evidence, ResearchRequest, ValidationIssue


ROOT = Path(__file__).parents[2]


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "shared" / name).read_text(encoding="utf-8"))


def make_request(**updates: object) -> ResearchRequest:
    payload = {**load_fixture("research_request.json"), **updates}
    return ResearchRequest.model_validate(payload)


def make_evidence(**updates: object) -> Evidence:
    payload = {**load_fixture("evidence.json"), **updates}
    return Evidence.model_validate(payload)


def make_claim(**updates: object) -> Claim:
    payload = {
        "claim_id": "CL-REPORT-001",
        "text": "报告披露本期营业收入同比增长 12.0%。",
        "claim_type": "fact",
        "evidence_ids": ["EV-FOOD-001"],
        "calculation": None,
        "confidence": 0.9,
        "industry_metric_ids": ["revenue_growth"],
        "status": "pass",
    }
    payload.update(updates)
    return Claim.model_validate(payload)


def make_unresolved_claim() -> Claim:
    return Claim(
        claim_id="CL-REPORT-UNRESOLVED",
        text="存货指标等待独立来源确认。",
        claim_type="unresolved",
        evidence_ids=[],
        calculation=None,
        confidence=0.0,
        industry_metric_ids=["inventory"],
        status="review",
    )


def make_issue() -> ValidationIssue:
    return ValidationIssue(
        issue_id="ISSUE-REPORT-001",
        check_name="test",
        severity="warning",
        issue_type="test_issue",
        message="测试校验问题。",
        claim_id=None,
        evidence_id=None,
        report_section=None,
        rerun_required=False,
        human_confirmation_required=False,
        status="open",
    )


def test_render_report_separates_claims_risks_and_unresolved() -> None:
    request = make_request()
    evidence = [make_evidence()]
    issue = make_issue()
    pass_fact = make_claim()
    review_change = make_claim(
        claim_id="CL-REPORT-CHANGE",
        text="监管部门发布食品安全相关政策。",
        claim_type="change",
        status="review",
    )
    pass_risk = make_claim(
        claim_id="CL-REPORT-RISK",
        text="库存压力需要结合收入和动销证据判断。",
        claim_type="risk",
        status="pass",
    )
    unresolved = make_unresolved_claim()
    rejected = make_claim(
        claim_id="CL-REPORT-REJECTED",
        text="这条被拒绝的结论不应出现在报告中。",
        claim_type="fact",
        status="reject",
    )
    claims = [pass_fact, review_change, pass_risk, unresolved, rejected]

    report = render_report(request, claims, evidence, [issue])

    assert [claim.claim_id for claim in report.claims] == [
        pass_fact.claim_id,
        review_change.claim_id,
    ]
    assert [claim.claim_id for claim in report.risks] == [pass_risk.claim_id]
    assert [claim.claim_id for claim in report.unresolved_items] == [unresolved.claim_id]
    assert report.evidence_index == evidence
    assert report.validation_issues == [issue]
    assert rejected.claim_id not in {
        claim.claim_id for claim in [*report.claims, *report.risks, *report.unresolved_items]
    }


def test_render_report_excludes_rejected_and_draft_claims() -> None:
    request = make_request()
    evidence = [make_evidence()]
    rejected = make_claim(status="reject", text="拒绝内容。")
    draft = make_claim(claim_id="CL-REPORT-DRAFT", claim_type="analysis", status="draft", text="草稿内容。")

    report = render_report(request, [rejected, draft], evidence, [])

    all_report_claims = [*report.claims, *report.risks, *report.unresolved_items]
    assert all_report_claims == []


def test_render_report_uses_a007_version_and_metadata_summary() -> None:
    request = make_request()
    evidence = [make_evidence()]
    report = render_report(request, [make_claim()], evidence, [])

    assert report.report_version == "v1-a007"
    assert report.run_id == request.run_id
    assert report.company_name == request.company_name
    assert any("正文结论" in item for item in report.summary)
    assert any("证据索引" in item for item in report.summary)


def test_render_markdown_contains_sections_and_excludes_rejected_claims() -> None:
    request = make_request()
    evidence = [make_evidence()]
    issue = make_issue()
    pass_fact = make_claim()
    review_change = make_claim(
        claim_id="CL-REPORT-CHANGE",
        text="监管部门发布食品安全相关政策。",
        claim_type="change",
        status="review",
    )
    pass_risk = make_claim(
        claim_id="CL-REPORT-RISK",
        text="库存压力需要结合收入和动销证据判断。",
        claim_type="risk",
        status="pass",
    )
    unresolved = make_unresolved_claim()
    rejected = make_claim(
        claim_id="CL-REPORT-REJECTED",
        text="被拒绝的结论不得出现在 Markdown 中。",
        claim_type="fact",
        status="reject",
    )
    claims = [pass_fact, review_change, pass_risk, unresolved, rejected]

    report = render_report(request, claims, evidence, [issue])
    markdown = render_markdown(report)

    assert "## 摘要" in markdown
    assert "## 正文结论" in markdown
    assert "## 风险" in markdown
    assert "## 待人工确认" in markdown
    assert "## 未决项" in markdown
    assert "## 证据索引" in markdown
    assert "## 校验问题" in markdown

    assert pass_fact.text in markdown
    assert review_change.text in markdown
    assert pass_risk.text in markdown
    assert unresolved.text in markdown
    assert issue.message in markdown
    assert evidence[0].locator in markdown
    assert rejected.text not in markdown


def test_render_markdown_marks_empty_sections_as_none() -> None:
    request = make_request()
    report = render_report(request, [], [], [])

    markdown = render_markdown(report)

    assert "- 无。" in markdown
