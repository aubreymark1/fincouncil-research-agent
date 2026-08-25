"""Tests for the A-006 Critic."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.agents import run_critic
from app.schemas import Claim, Evidence, IndustryConfig, ResearchRequest


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
        "claim_id": "CL-CRITIC-001",
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
        claim_id="CL-CRITIC-INVENTORY",
        text="存货指标等待独立来源确认。",
        claim_type="unresolved",
        evidence_ids=[],
        calculation=None,
        confidence=0.0,
        industry_metric_ids=["inventory"],
        status="review",
    )


def test_valid_pass_claim_produces_no_issues() -> None:
    request = make_request()
    evidence = [make_evidence()]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claims = [make_claim(), make_unresolved_claim()]

    issues = run_critic(request, claims, evidence, config)

    assert issues == []


def test_cutoff_violation_is_critical() -> None:
    request = make_request(cutoff_date=date(2026, 8, 20))
    evidence = [make_evidence(evidence_id="EV-LATE-001", published_at="2026-08-25")]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))

    issues = run_critic(request, [], evidence, config)

    cutoff = [issue for issue in issues if issue.issue_type == "cutoff_violation"]
    assert len(cutoff) == 1
    assert cutoff[0].severity == "critical"
    assert cutoff[0].evidence_id == "EV-LATE-001"


def test_claim_without_evidence_is_reported() -> None:
    request = make_request()
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = Claim.model_construct(
        claim_id="CL-CRITIC-NO-EVIDENCE",
        text="这是一个没有证据支撑的事实。",
        claim_type="fact",
        evidence_ids=[],
        calculation=None,
        confidence=0.8,
        industry_metric_ids=["revenue_growth"],
        status="pass",
    )

    issues = run_critic(request, [claim], [], config)

    missing = [issue for issue in issues if issue.issue_type == "missing_evidence"]
    assert len(missing) == 1
    assert missing[0].claim_id == claim.claim_id
    assert missing[0].severity == "error"


def test_unknown_evidence_id_is_reported() -> None:
    request = make_request()
    evidence = [make_evidence()]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(evidence_ids=["EV-MISSING-001"])

    issues = run_critic(request, [claim], evidence, config)

    unknown = [issue for issue in issues if issue.issue_type == "unknown_evidence_id"]
    assert len(unknown) == 1
    assert unknown[0].evidence_id == "EV-MISSING-001"
    assert unknown[0].claim_id == claim.claim_id


def test_unsourced_number_is_reported() -> None:
    request = make_request()
    evidence = [make_evidence(fact_text="公司收入保持稳定。", quote="公司收入保持稳定。")]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(
        text="公司收入增长 25%。",
        evidence_ids=[evidence[0].evidence_id],
        industry_metric_ids=["revenue_growth"],
    )

    issues = run_critic(request, [claim], evidence, config)

    unsourced = [issue for issue in issues if issue.issue_type == "unsourced_number"]
    assert len(unsourced) == 1
    assert "25%" in unsourced[0].message


def test_sourced_number_is_accepted() -> None:
    request = make_request()
    evidence = [make_evidence()]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(
        text="报告披露本期营业收入同比增长 12.0%。",
        evidence_ids=["EV-FOOD-001"],
        industry_metric_ids=["revenue_growth"],
    )

    issues = run_critic(request, [claim], evidence, config)

    unsourced = [issue for issue in issues if issue.issue_type == "unsourced_number"]
    assert unsourced == []


def test_missing_locator_and_page_are_reported() -> None:
    request = make_request()
    evidence = [make_evidence(page=None, locator="   ")]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(evidence_ids=[evidence[0].evidence_id])

    issues = run_critic(request, [claim], evidence, config)

    assert any(issue.issue_type == "missing_locator" for issue in issues)
    assert any(issue.issue_type == "missing_page" for issue in issues)


def test_management_plan_as_fact_is_warned() -> None:
    request = make_request()
    evidence = [make_evidence()]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(
        text="公司计划在明年实现收入增长 20%。",
        evidence_ids=["EV-FOOD-001"],
        industry_metric_ids=["revenue_growth"],
    )

    issues = run_critic(request, [claim], evidence, config)

    plan = [issue for issue in issues if issue.issue_type == "management_plan_as_fact"]
    assert len(plan) == 1
    assert plan[0].severity == "warning"
    assert plan[0].human_confirmation_required is True


def test_required_metric_missing_is_reported() -> None:
    request = make_request()
    evidence = [make_evidence()]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(industry_metric_ids=["inventory"])

    issues = run_critic(request, [claim], evidence, config)

    missing = [
        issue
        for issue in issues
        if issue.issue_type == "required_metric_missing"
        and "revenue_growth" in issue.message
    ]
    assert len(missing) == 1
    assert missing[0].severity == "error"


def test_conflicting_evidence_inside_claim_is_reported() -> None:
    request = make_request()
    up = make_evidence(
        evidence_id="EV-UP-001",
        fact_text="公司收入增长 10%。",
        quote="收入增长 10%。",
    )
    down = make_evidence(
        evidence_id="EV-DOWN-001",
        fact_text="公司收入下降 5%。",
        quote="收入下降 5%。",
    )
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(
        claim_id="CL-CRITIC-CONFLICT",
        evidence_ids=["EV-UP-001", "EV-DOWN-001"],
        text="公司收入波动。",
        industry_metric_ids=["revenue_growth"],
    )

    issues = run_critic(request, [claim], [up, down], config)

    conflicts = [
        issue
        for issue in issues
        if issue.issue_type == "conflicting_evidence"
        and issue.claim_id == claim.claim_id
    ]
    assert len(conflicts) == 1
    assert conflicts[0].human_confirmation_required is True


def test_conflicting_evidence_across_claims_is_reported() -> None:
    request = make_request()
    up_evidence = make_evidence(
        evidence_id="EV-UP-002",
        fact_text="公司收入增长 10%。",
        quote="收入增长 10%。",
    )
    down_evidence = make_evidence(
        evidence_id="EV-DOWN-002",
        fact_text="公司收入下降 5%。",
        quote="收入下降 5%。",
    )
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    up_claim = make_claim(
        claim_id="CL-CRITIC-UP",
        evidence_ids=["EV-UP-002"],
        text="公司收入增长 10%。",
        industry_metric_ids=["revenue_growth"],
    )
    down_claim = make_claim(
        claim_id="CL-CRITIC-DOWN",
        evidence_ids=["EV-DOWN-002"],
        text="公司收入下降 5%。",
        industry_metric_ids=["revenue_growth"],
    )

    issues = run_critic(request, [up_claim, down_claim], [up_evidence, down_evidence], config)

    conflicts = [
        issue
        for issue in issues
        if issue.issue_type == "conflicting_evidence"
        and "revenue_growth" in issue.message
    ]
    assert len(conflicts) == 1
    assert up_claim.claim_id in conflicts[0].message
    assert down_claim.claim_id in conflicts[0].message


def test_draft_model_output_is_reported() -> None:
    request = make_request()
    evidence = [make_evidence()]
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    claim = make_claim(status="draft", claim_type="analysis")

    issues = run_critic(request, [claim], evidence, config)

    unparsed = [issue for issue in issues if issue.issue_type == "model_output_unparsed"]
    assert len(unparsed) == 1
    assert unparsed[0].severity == "error"
