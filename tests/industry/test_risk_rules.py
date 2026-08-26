"""Tests for C-003 industry risk rule application."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.industry import apply_risk_rules, load_industry_config
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    MetricRule,
    RiskRule,
    SourceDocument,
)


def make_metric(
    metric_id: str = "revenue_growth",
    display_name: str = "收入增速",
    keywords: list[str] | None = None,
    evidence_types: list[str] | None = None,
    required: bool = True,
    evidence_requirement: str = "single",
    missing_action: str = "review",
) -> MetricRule:
    return MetricRule(
        metric_id=metric_id,
        display_name=display_name,
        keywords=keywords if keywords is not None else ["收入", "营业收入"],
        evidence_types=evidence_types or ["financial"],
        required=required,
        evidence_requirement=evidence_requirement,  # type: ignore[arg-type]
        missing_action=missing_action,  # type: ignore[arg-type]
    )


def make_risk_rule(
    risk_id: str = "inventory_pressure",
    display_name: str = "库存压力",
    trigger_description: str = "库存变化需要结合收入和动销证据判断。",
    metric_ids: list[str] | None = None,
    required_evidence_types: list[str] | None = None,
    severity: str = "medium",
) -> RiskRule:
    return RiskRule(
        risk_id=risk_id,
        display_name=display_name,
        trigger_description=trigger_description,
        metric_ids=metric_ids or ["inventory", "revenue_growth"],
        required_evidence_types=required_evidence_types or ["financial", "operating"],
        severity=severity,  # type: ignore[arg-type]
    )


def make_config(
    *metrics: MetricRule,
    risk_rules: list[RiskRule] | None = None,
) -> IndustryConfig:
    if not metrics:
        metrics = (
            make_metric(metric_id="inventory", display_name="存货", keywords=["存货", "库存"]),
            make_metric(metric_id="revenue_growth", display_name="收入增速", keywords=["收入", "营业收入"]),
        )
    return IndustryConfig(
        industry_id="food_beverage",
        display_name="测试食品饮料",
        required_metrics=list(metrics),
        event_taxonomy=["业绩"],
        risk_rules=[make_risk_rule()] if risk_rules is None else risk_rules,
        report_sections=["summary", "risks"],
        retrieval_keywords=["收入", "存货"],
    )


def make_evidence(
    evidence_id: str = "E1",
    text: str = "报告披露存货增速高于收入增速。",
    evidence_type: str = "financial",
    review_status: str = "verified",
    industry_id: str = "food_beverage",
) -> Evidence:
    return Evidence(
        evidence_id=f"EV-{evidence_id}",
        doc_id="DOC-A",
        chunk_id="CHUNK-A-001",
        fact_text=text,
        quote=text,
        published_at=date(2026, 1, 1),
        page=1,
        section="风险分析",
        locator="page 1",
        company_name="测试公司",
        industry_id=industry_id,
        evidence_type=evidence_type,  # type: ignore[arg-type]
        confidence=0.5,
        review_status=review_status,  # type: ignore[arg-type]
    )


def test_food_and_banking_risk_rules_differ() -> None:
    food = load_industry_config("food_beverage")
    banking = load_industry_config("banking")

    food_risk_ids = {rule.risk_id for rule in food.risk_rules}
    banking_risk_ids = {rule.risk_id for rule in banking.risk_rules}

    assert food_risk_ids
    assert banking_risk_ids
    assert food_risk_ids.isdisjoint(banking_risk_ids)


def test_empty_risk_rules_return_no_claims() -> None:
    config = make_config(risk_rules=[])

    claims = apply_risk_rules([], config)

    assert claims == []


def test_missing_required_evidence_type_returns_unresolved() -> None:
    config = make_config()
    evidence = [make_evidence(evidence_type="financial")]

    claims = apply_risk_rules(evidence, config)

    assert len(claims) == 1
    assert claims[0].claim_type == "unresolved"
    assert claims[0].status == "review"
    assert "operating" in claims[0].text


def test_risk_claim_generated_when_all_types_and_trigger_content_present() -> None:
    config = make_config()
    evidence = [
        make_evidence("E1", text="报告披露存货增速高于收入增速。", evidence_type="financial"),
        make_evidence("E2", text="公司披露渠道库存压力上升。", evidence_type="operating"),
    ]

    claims = apply_risk_rules(evidence, config)

    assert len(claims) == 1
    claim = claims[0]
    assert isinstance(claim, Claim)
    assert claim.claim_type == "risk"
    assert claim.status == "review"
    assert claim.risk_severity == "medium"
    assert set(claim.industry_metric_ids) == {"inventory", "revenue_growth"}
    assert set(claim.evidence_ids) == {"EV-E1", "EV-E2"}


def test_risk_claim_requires_trigger_content_for_each_type() -> None:
    config = make_config()
    evidence = [
        make_evidence("E1", text="公司员工数量保持稳定。", evidence_type="financial"),
        make_evidence("E2", text="公司披露渠道库存压力上升。", evidence_type="operating"),
    ]

    claims = apply_risk_rules(evidence, config)

    assert len(claims) == 1
    assert claims[0].claim_type == "unresolved"
    assert "financial" in claims[0].text


def test_risk_claim_excludes_pending_and_cross_industry_evidence() -> None:
    config = make_config()
    evidence = [
        make_evidence("E1", text="报告披露存货增速高于收入增速。", evidence_type="financial"),
        make_evidence("E2", text="公司披露渠道库存压力上升。", evidence_type="operating", review_status="pending"),
        make_evidence("E3", text="其他行业库存风险上升。", evidence_type="operating", industry_id="banking"),
    ]

    claims = apply_risk_rules(evidence, config)

    assert len(claims) == 1
    assert claims[0].claim_type == "unresolved"
    assert "operating" in claims[0].text


def test_risk_claim_does_not_include_stock_price_judgment() -> None:
    config = make_config()
    evidence = [
        make_evidence("E1", text="报告披露存货增速高于收入增速。", evidence_type="financial"),
        make_evidence("E2", text="公司披露渠道库存压力上升。", evidence_type="operating"),
    ]

    claims = apply_risk_rules(evidence, config)

    assert claims[0].claim_type == "risk"
    assert "目标价" not in claims[0].text
    assert "股价" not in claims[0].text
