"""Tests for the A-005 evidence-bound analysis nodes."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents import analyze_fundamentals, analyze_news_policy, analyze_risks
from app.schemas import Evidence, IndustryConfig


ROOT = Path(__file__).parents[2]


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "shared" / name).read_text(encoding="utf-8"))


def make_evidence(**updates: object) -> Evidence:
    payload = {**load_fixture("evidence.json"), **updates}
    return Evidence.model_validate(payload)


def test_fundamentals_only_pass_when_metric_evidence_is_sufficient() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    evidence = [make_evidence()]

    claims = analyze_fundamentals(evidence, config)

    revenue_claim = next(claim for claim in claims if claim.claim_id == "CL-FUND-revenue_growth")
    inventory_claim = next(claim for claim in claims if claim.claim_id == "CL-FUND-inventory")
    assert revenue_claim.claim_type == "fact"
    assert revenue_claim.status == "pass"
    assert revenue_claim.evidence_ids == ["EV-FOOD-001"]
    assert inventory_claim.claim_type == "unresolved"
    assert inventory_claim.status == "review"


def test_fundamentals_require_two_distinct_documents_for_multiple_metrics() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    first = make_evidence(
        evidence_id="EV-FOOD-INVENTORY-001",
        fact_text="公司披露存货余额保持稳定。",
        quote="存货余额保持稳定。",
        evidence_type="financial",
    )
    same_document = make_evidence(
        evidence_id="EV-FOOD-INVENTORY-002",
        fact_text="公司披露库存周转情况。",
        quote="库存周转情况。",
        evidence_type="operating",
    )

    claims = analyze_fundamentals([first, same_document], config)

    inventory_claim = next(claim for claim in claims if claim.claim_id == "CL-FUND-inventory")
    assert inventory_claim.claim_type == "unresolved"
    assert "两个独立来源" in inventory_claim.text


def test_news_policy_excludes_pending_and_rejected_evidence() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    pending = make_evidence(evidence_id="EV-NEWS-PENDING", evidence_type="policy", review_status="pending")
    rejected = make_evidence(evidence_id="EV-NEWS-REJECTED", evidence_type="news", review_status="rejected")

    claims = analyze_news_policy([pending, rejected], config)

    assert len(claims) == 1
    assert claims[0].claim_type == "unresolved"
    assert claims[0].evidence_ids == []


def test_news_policy_returns_reviewable_change_claim_for_verified_policy() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    policy = make_evidence(
        evidence_id="EV-POLICY-001",
        fact_text="监管部门发布食品安全相关政策。",
        quote="发布食品安全相关政策。",
        evidence_type="policy",
    )

    claims = analyze_news_policy([policy], config)

    assert claims[0].claim_type == "change"
    assert claims[0].status == "review"
    assert claims[0].evidence_ids == ["EV-POLICY-001"]


def test_risk_requires_all_configured_evidence_types() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    financial = make_evidence(evidence_type="financial")

    claims = analyze_risks([financial], config)

    assert len(claims) == 1
    assert claims[0].claim_type == "unresolved"
    assert "operating" in claims[0].text


def test_risk_returns_review_claim_when_all_evidence_types_exist() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    financial = make_evidence(evidence_type="financial")
    operating = make_evidence(
        evidence_id="EV-FOOD-OPERATING-001",
        fact_text="公司披露渠道动销情况。",
        quote="渠道动销情况。",
        evidence_type="operating",
    )

    claims = analyze_risks([financial, operating], config)

    assert claims[0].claim_type == "risk"
    assert claims[0].status == "review"
    assert set(claims[0].evidence_ids) == {"EV-FOOD-001", "EV-FOOD-OPERATING-001"}
