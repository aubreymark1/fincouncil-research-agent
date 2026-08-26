"""Tests for the A-005 evidence-bound analysis nodes."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents import analyze_fundamentals, analyze_news_policy, analyze_risks
from app.industry import apply_risk_rules, check_required_metrics
from app.schemas import Evidence, IndustryConfig, SourceDocument


ROOT = Path(__file__).parents[2]


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "shared" / name).read_text(encoding="utf-8"))


def make_evidence(**updates: object) -> Evidence:
    payload = {**load_fixture("evidence.json"), **updates}
    return Evidence.model_validate(payload)


def make_document(**updates: object) -> SourceDocument:
    payload = {**load_fixture("source_document.json"), **updates}
    return SourceDocument.model_validate(payload)


def test_fundamentals_only_pass_when_metric_evidence_is_sufficient() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    evidence = [make_evidence()]

    claims = analyze_fundamentals(evidence, config)

    revenue_claim = next(claim for claim in claims if claim.claim_id.startswith("CL-FUND-REVENUE-GROWTH-"))
    inventory_claim = next(claim for claim in claims if claim.claim_id.startswith("CL-FUND-INVENTORY-"))
    assert revenue_claim.claim_type == "fact"
    assert revenue_claim.status == "pass"
    assert revenue_claim.evidence_ids == ["EV-FOOD-001"]
    assert inventory_claim.claim_type == "unresolved"
    assert inventory_claim.status == "review"


def test_fundamentals_reject_disallowed_evidence_type_even_with_keyword() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    policy_evidence = make_evidence(
        evidence_id="EV-POLICY-REVENUE-001",
        fact_text="监管部门报告营业收入增长 12%。",
        quote="营业收入增长 12%。",
        evidence_type="policy",
    )

    claims = analyze_fundamentals([policy_evidence], config)

    revenue_claim = next(
        claim for claim in claims if claim.claim_id.startswith("CL-FUND-REVENUE-GROWTH-")
    )
    assert revenue_claim.claim_type == "unresolved"
    assert revenue_claim.status == "review"
    assert revenue_claim.evidence_ids == []


def test_checklist_and_fundamentals_agree_on_whitespace_keywords() -> None:
    payload = load_fixture("food_config.json")
    payload["required_metrics"][0]["keywords"] = [" 营业收入 "]
    config = IndustryConfig.model_validate(payload)
    evidence = [make_evidence()]
    documents = [make_document()]

    checklist_issues = check_required_metrics(evidence, config, documents=documents)
    claims = analyze_fundamentals(evidence, config, documents=documents)

    revenue_claim = next(
        claim for claim in claims if claim.claim_id.startswith("CL-FUND-REVENUE-GROWTH-")
    )
    assert revenue_claim.claim_type == "fact"
    assert revenue_claim.status == "pass"
    assert not any("revenue_growth" in issue.message for issue in checklist_issues)


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
        doc_id="DOC-FOOD-002",
        fact_text="公司披露库存周转情况。",
        quote="库存周转情况。",
        evidence_type="operating",
    )

    claims = analyze_fundamentals([first, same_document], config)

    inventory_claim = next(claim for claim in claims if claim.claim_id.startswith("CL-FUND-INVENTORY-"))
    assert inventory_claim.claim_type == "unresolved"
    assert "独立发布主体" in inventory_claim.text


def test_multiple_metric_passes_with_independent_source_documents() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    first = make_evidence(
        evidence_id="EV-FOOD-INVENTORY-101",
        doc_id="DOC-FOOD-001",
        fact_text="公司披露存货余额保持稳定。",
        quote="存货余额保持稳定。",
        evidence_type="financial",
    )
    second = make_evidence(
        evidence_id="EV-FOOD-INVENTORY-102",
        doc_id="DOC-FOOD-002",
        fact_text="独立机构跟踪库存周转改善。",
        quote="库存周转改善。",
        evidence_type="operating",
    )
    documents = [
        make_document(),
        make_document(
            doc_id="DOC-FOOD-002",
            publisher="独立研究机构",
            content_hash="sha256:independent-source",
        ),
    ]

    claims = analyze_fundamentals(
        [first, second],
        config,
        documents=documents,
    )

    inventory_claim = next(
        claim for claim in claims if claim.claim_id.startswith("CL-FUND-INVENTORY-")
    )
    assert inventory_claim.claim_type == "fact"
    assert inventory_claim.status == "pass"


def test_cross_industry_and_unknown_industry_evidence_are_excluded() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    cross_industry = make_evidence(evidence_id="EV-BANK-001", industry_id="banking")
    unknown_industry = make_evidence(evidence_id="EV-GENERIC-001", industry_id=None)

    fundamental_claims = analyze_fundamentals([cross_industry, unknown_industry], config)
    news_claims = analyze_news_policy(
        [cross_industry.model_copy(update={"evidence_type": "policy"}), unknown_industry],
        config,
    )
    risk_claims = analyze_risks([cross_industry, unknown_industry], config)

    assert all(claim.claim_type == "unresolved" for claim in fundamental_claims)
    assert news_claims[0].claim_type == "unresolved"
    assert risk_claims[0].claim_type == "unresolved"


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
    financial = make_evidence(
        evidence_id="EV-FOOD-INVENTORY-001",
        fact_text="报告披露存货增速高于收入增速。",
        quote="存货增速高于收入增速。",
        evidence_type="financial",
    )
    operating = make_evidence(
        evidence_id="EV-FOOD-OPERATING-001",
        fact_text="公司披露渠道库存压力上升。",
        quote="渠道库存压力上升。",
        evidence_type="operating",
    )

    claims = analyze_risks([financial, operating], config)

    assert claims[0].claim_type == "risk"
    assert claims[0].status == "review"
    assert claims[0].risk_severity == "medium"
    assert set(claims[0].industry_metric_ids) == {"inventory", "revenue_growth"}
    assert set(claims[0].evidence_ids) == {"EV-FOOD-INVENTORY-001", "EV-FOOD-OPERATING-001"}


def test_risk_requires_trigger_content_not_only_evidence_types() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    financial = make_evidence(evidence_type="financial")
    operating = make_evidence(
        evidence_id="EV-FOOD-OPERATING-002",
        fact_text="公司披露渠道动销情况。",
        quote="渠道动销情况。",
        evidence_type="operating",
    )

    claims = analyze_risks([financial, operating], config)

    assert claims[0].claim_type == "unresolved"
    assert "financial" in claims[0].text


def test_risk_requires_trigger_content_for_each_evidence_type() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    financial = make_evidence(
        evidence_id="EV-FOOD-INVENTORY-004",
        fact_text="报告披露存货增速高于收入增速。",
        quote="存货增速高于收入增速。",
        evidence_type="financial",
    )
    unrelated_operating = make_evidence(
        evidence_id="EV-FOOD-OPERATING-004",
        fact_text="公司完成员工培训。",
        quote="完成员工培训。",
        evidence_type="operating",
    )

    claims = analyze_risks([financial, unrelated_operating], config)

    assert claims[0].claim_type == "unresolved"
    assert "operating" in claims[0].text


def test_analyze_risks_matches_apply_risk_rules() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    evidence = [
        make_evidence(
            evidence_id="EV-FOOD-INVENTORY-001",
            fact_text="报告披露存货增速高于收入增速。",
            quote="存货增速高于收入增速。",
            evidence_type="financial",
        ),
        make_evidence(
            evidence_id="EV-FOOD-OPERATING-001",
            fact_text="公司披露渠道库存压力上升。",
            quote="渠道库存压力上升。",
            evidence_type="operating",
        ),
    ]

    from_agent = analyze_risks(evidence, config)
    from_c = apply_risk_rules(evidence, config)

    assert [
        (claim.claim_type, claim.status, sorted(claim.evidence_ids))
        for claim in from_agent
    ] == [
        (claim.claim_type, claim.status, sorted(claim.evidence_ids))
        for claim in from_c
    ]


def test_claim_ids_are_legal_for_unicode_and_special_metric_ids() -> None:
    payload = load_fixture("food_config.json")
    old_metric_id = payload["required_metrics"][0]["metric_id"]
    new_metric_id = "收入 增速/同比"
    payload["required_metrics"][0]["metric_id"] = new_metric_id
    payload["required_metrics"][0]["keywords"] = ["营业收入"]
    payload["risk_rules"][0]["metric_ids"] = [
        new_metric_id if metric_id == old_metric_id else metric_id
        for metric_id in payload["risk_rules"][0]["metric_ids"]
    ]
    config = IndustryConfig.model_validate(payload)

    claims = analyze_fundamentals([make_evidence()], config)

    assert claims[0].claim_id.startswith("CL-FUND-")
    assert claims[0].claim_id.replace("-", "").isalnum()
