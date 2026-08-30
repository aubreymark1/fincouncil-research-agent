"""Tests for the A-007 formal report renderer."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents import render_markdown, render_report
from app.schemas import Claim, Evidence, NarrativeBlock, NarrativeSegment, ResearchRequest, ValidationIssue


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
    if payload["claim_type"] == "risk" and payload.get("risk_severity") is None:
        payload["risk_severity"] = "medium"
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


def make_issue(**updates: object) -> ValidationIssue:
    payload = {
        "issue_id": "ISSUE-REPORT-001",
        "check_name": "test",
        "severity": "warning",
        "issue_type": "test_issue",
        "message": "测试校验问题。",
        "claim_id": None,
        "evidence_id": None,
        "report_section": None,
        "rerun_required": False,
        "human_confirmation_required": False,
        "status": "open",
    }
    payload.update(updates)
    return ValidationIssue.model_validate(payload)


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

    assert len(report.narrative) == 2
    assert report.narrative[0].section == "核心判断"
    assert {segment.text for segment in report.narrative[0].segments} == {pass_fact.text}
    assert report.narrative[0].segments[0].evidence_ids == pass_fact.evidence_ids
    assert report.narrative[1].section == "风险与待确认"
    assert {segment.text for segment in report.narrative[1].segments} == {
        pass_risk.text,
    }


def test_render_report_preserves_llm_narrative_segments() -> None:
    request = make_request()
    evidence = [make_evidence()]
    claim = make_claim()
    narrative = [
        NarrativeBlock(
            section="核心判断",
            segments=[
                NarrativeSegment(
                    segment_id="SEG-LLM-001",
                    text="经过组织的正文句子。",
                    evidence_ids=[evidence[0].evidence_id],
                    claim_type="fact",
                    status="pass",
                )
            ],
        )
    ]

    report = render_report(request, [claim], evidence, [], narrative=narrative)

    assert report.narrative == narrative


def test_render_report_excludes_rejected_and_draft_claims() -> None:
    request = make_request()
    evidence = [make_evidence()]
    rejected = make_claim(status="reject", text="拒绝内容。")
    draft = make_claim(claim_id="CL-REPORT-DRAFT", claim_type="analysis", status="draft", text="草稿内容。")

    report = render_report(request, [rejected, draft], evidence, [])

    all_report_claims = [*report.claims, *report.risks, *report.unresolved_items]
    assert all_report_claims == []


def test_render_report_uses_a008_version_and_metadata_summary() -> None:
    request = make_request()
    evidence = [make_evidence()]
    report = render_report(request, [make_claim()], evidence, [])

    assert report.report_version == "v1-a008"
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
    assert "## 投研正文" in markdown
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


def test_pass_claim_with_critical_issue_is_downgraded_out_of_body() -> None:
    request = make_request()
    evidence = [make_evidence()]
    claim = make_claim()
    issue = make_issue(
        severity="critical",
        claim_id=claim.claim_id,
        message="该 Claim 存在截止日期违规。",
    )

    report = render_report(request, [claim], evidence, [issue])
    markdown = render_markdown(report)

    rendered_claim = next(item for item in report.claims if item.claim_id == claim.claim_id)
    assert rendered_claim.status == "review"

    body_section = markdown.split("## 待人工确认")[0]
    pending_section = markdown.split("## 待人工确认")[1].split("## 未决项")[0]
    assert claim.text not in body_section
    assert claim.text in pending_section


def test_pass_claim_with_error_on_evidence_is_downgraded() -> None:
    request = make_request()
    evidence = [make_evidence()]
    claim = make_claim()
    issue = make_issue(
        severity="error",
        evidence_id="EV-FOOD-001",
        message="该证据为 rejected，不能支撑正文。",
    )

    report = render_report(request, [claim], evidence, [issue])

    rendered_claim = next(item for item in report.claims if item.claim_id == claim.claim_id)
    assert rendered_claim.status == "review"


def test_evidence_index_only_includes_referenced_verified_evidence() -> None:
    request = make_request()
    referenced_verified = make_evidence(evidence_id="EV-FOOD-001")
    unreferenced_verified = make_evidence(
        evidence_id="EV-FOOD-UNUSED",
        fact_text="未引用的正常证据。",
        quote="未引用的正常证据。",
    )
    rejected = make_evidence(
        evidence_id="EV-FOOD-REJECTED",
        fact_text="被拒绝的证据。",
        quote="被拒绝的证据。",
        review_status="rejected",
    )
    claim = make_claim(evidence_ids=["EV-FOOD-001"])

    report = render_report(
        request,
        [claim],
        [referenced_verified, unreferenced_verified, rejected],
        [],
    )

    assert [item.evidence_id for item in report.evidence_index] == ["EV-FOOD-001"]
    assert unreferenced_verified.evidence_id not in {
        item.evidence_id for item in report.evidence_index
    }
    assert rejected.evidence_id not in {
        item.evidence_id for item in report.evidence_index
    }


def test_summary_counts_pass_and_review_separately() -> None:
    request = make_request()
    evidence = [make_evidence()]
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
    review_risk = make_claim(
        claim_id="CL-REPORT-RISK-REVIEW",
        text="新的风险信号需要人工确认。",
        claim_type="risk",
        status="review",
    )
    unresolved = make_unresolved_claim()

    report = render_report(
        request,
        [pass_fact, review_change, pass_risk, review_risk, unresolved],
        evidence,
        [],
    )

    assert any("1 条正文结论、1 条风险" in line for line in report.summary)
    assert any("2 条待人工确认" in line and "1 个未决项" in line for line in report.summary)


def test_render_markdown_marks_empty_sections_as_none() -> None:
    request = make_request()
    report = render_report(request, [], [], [])

    markdown = render_markdown(report)

    assert "- 无。" in markdown
