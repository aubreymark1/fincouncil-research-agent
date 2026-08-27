"""Unit tests for the run_analysis aggregation entry point."""

from __future__ import annotations

from datetime import date

from app.agents.aggregation import run_analysis
from app.industry.loader import load_industry_config
from app.schemas import Claim, Evidence, ResearchRequest


def make_request() -> ResearchRequest:
    return ResearchRequest(
        run_id="RUN-AGG",
        company_name="示例食品公司",
        industry_id="food_beverage",
        cutoff_date=date(2026, 8, 20),
        source_manifest_path="data/manifests/food_case.csv",
        output_dir="outputs/reports/RUN-AGG",
    )


def make_verified_financial_evidence() -> Evidence:
    return Evidence.model_validate(
        {
            "evidence_id": "EV-AGG-FINANCIAL-ABCD1234-0",
            "doc_id": "DOC-FOOD-001",
            "chunk_id": "CHUNK-FOOD-001-P1",
            "fact_text": "报告期内公司营业收入同比增长 10%。",
            "quote": "报告期内公司营业收入同比增长 10%。",
            "published_at": date(2026, 4, 17),
            "page": 1,
            "locator": "page 1, chunk CHUNK-FOOD-001-P1",
            "company_name": "贵州茅台酒股份有限公司",
            "industry_id": "food_beverage",
            "evidence_type": "financial",
            "confidence": 0.5,
            "review_status": "verified",
        }
    )


def test_run_analysis_concatenates_all_three_nodes():
    # Arrange
    request = make_request()
    config = load_industry_config("food_beverage")
    evidence = [make_verified_financial_evidence()]

    # Act
    claims = run_analysis(request, evidence, config, documents=[])

    # Assert
    fundamental_ids = {claim.claim_id.split("-")[1] for claim in claims}
    assert "FUND" in fundamental_ids
    assert any(claim.claim_id == "CL-NEWS-POLICY-UNRESOLVED" for claim in claims)
    # One unresolved risk claim per configured rule when nothing triggers.
    expected_risk_count = len(config.risk_rules)
    assert (
        sum(claim.claim_type == "risk" or claim.claim_type == "unresolved" for claim in claims)
        >= expected_risk_count
    )


def test_run_analysis_yields_pass_claim_for_matched_metric():
    # Arrange
    request = make_request()
    config = load_industry_config("food_beverage")

    # Act
    claims = run_analysis(request, [make_verified_financial_evidence()], config, documents=[])

    # Assert
    matched = [
        claim
        for claim in claims
        if claim.status == "pass" and "revenue_growth" in claim.industry_metric_ids
    ]
    assert len(matched) == 1
    assert isinstance(matched[0], Claim)
