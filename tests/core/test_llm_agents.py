"""Tests for the LLM-powered agent nodes (ADAPT-008)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents import (
    analyze_fundamentals_llm,
    analyze_news_policy_llm,
    analyze_risks_llm,
    get_prompt_versions,
    run_analysis,
    run_critic_llm,
)
from app.model import InMemoryCache, ModelConfig, ModelProvider, ModelProviderError
from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchRequest,
    SourceDocument,
    ValidationIssue,
)


ROOT = Path(__file__).parents[2]


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "shared" / name).read_text(encoding="utf-8"))


def make_request(**updates: object) -> ResearchRequest:
    payload = {**load_fixture("research_request.json"), **updates}
    return ResearchRequest.model_validate(payload)


def make_evidence(**updates: object) -> Evidence:
    payload = {**load_fixture("evidence.json"), **updates}
    return Evidence.model_validate(payload)


def make_document(**updates: object) -> SourceDocument:
    payload = {**load_fixture("source_document.json"), **updates}
    return SourceDocument.model_validate(payload)


def make_config() -> IndustryConfig:
    return IndustryConfig.model_validate(load_fixture("food_config.json"))


def make_claim_payload(**updates: object) -> dict:
    payload = {
        "claim_id": "CL-LLM-001",
        "text": "报告披露本期营业收入同比增长 12.0%。",
        "claim_type": "fact",
        "risk_severity": None,
        "evidence_ids": ["EV-FOOD-001"],
        "calculation": None,
        "confidence": 0.9,
        "industry_metric_ids": ["revenue_growth"],
        "status": "pass",
    }
    payload.update(updates)
    return payload


def make_issue_payload() -> dict:
    return {
        "issue_id": "ISSUE-LLM-001",
        "check_name": "llm_test",
        "severity": "warning",
        "issue_type": "test_issue",
        "message": "LLM critic test issue。",
        "claim_id": None,
        "evidence_id": None,
        "report_section": None,
        "rerun_required": False,
        "human_confirmation_required": False,
        "status": "open",
    }


def make_provider(transport) -> ModelProvider:
    return ModelProvider(ModelConfig(max_retries=0), transport=transport)


def test_analyze_fundamentals_llm_uses_provider_and_returns_claims() -> None:
    captured: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        captured.append(prompt)
        return {"claims": [make_claim_payload()]}

    provider = make_provider(transport)
    evidence = [make_evidence()]
    config = make_config()
    request = make_request()

    claims = analyze_fundamentals_llm(provider, request, evidence, config)

    assert len(claims) == 1
    assert isinstance(claims[0], Claim)
    assert claims[0].claim_id == "CL-LLM-001"
    assert "基本面分析提示词" in captured[0]
    assert "示例食品公司" in captured[0]


def test_llm_analysis_filters_pending_and_cross_industry_evidence() -> None:
    captured: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        captured.append(prompt)
        return {"claims": [make_claim_payload()]}

    provider = make_provider(transport)
    evidence = [
        make_evidence(),
        make_evidence(evidence_id="EV-PENDING-001", review_status="pending"),
        make_evidence(evidence_id="EV-BANK-001", industry_id="banking"),
    ]
    config = make_config()
    request = make_request()

    analyze_fundamentals_llm(provider, request, evidence, config)

    assert "EV-FOOD-001" in captured[0]
    assert "EV-PENDING-001" not in captured[0]
    assert "EV-BANK-001" not in captured[0]


def test_news_policy_llm_excludes_financial_evidence() -> None:
    captured: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        captured.append(prompt)
        return {"claims": [make_claim_payload(claim_type="change", status="review")]}

    provider = make_provider(transport)
    financial = make_evidence(evidence_id="EV-FIN-001", evidence_type="financial")
    news = make_evidence(evidence_id="EV-NEWS-001", evidence_type="news")
    config = make_config()
    request = make_request()

    analyze_news_policy_llm(provider, request, [financial, news], config)

    assert "EV-NEWS-001" in captured[0]
    assert "EV-FIN-001" not in captured[0]


def test_risk_llm_excludes_non_rule_evidence_types() -> None:
    captured: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        captured.append(prompt)
        return {
            "claims": [
                make_claim_payload(
                    claim_id="CL-LLM-RISK",
                    claim_type="risk",
                    risk_severity="medium",
                    status="review",
                    evidence_ids=["EV-FIN-001", "EV-OP-001"],
                )
            ]
        }

    provider = make_provider(transport)
    financial = make_evidence(evidence_id="EV-FIN-001", evidence_type="financial")
    operating = make_evidence(evidence_id="EV-OP-001", evidence_type="operating")
    policy = make_evidence(evidence_id="EV-POLICY-001", evidence_type="policy")
    config = make_config()
    request = make_request()

    analyze_risks_llm(provider, request, [financial, operating, policy], config)

    assert "EV-FIN-001" in captured[0]
    assert "EV-OP-001" in captured[0]
    assert "EV-POLICY-001" not in captured[0]


def test_cache_invalidates_when_prompt_changes(monkeypatch) -> None:
    calls: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        calls.append(prompt)
        return {"claims": [make_claim_payload()]}

    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=transport,
        cache=InMemoryCache(),
    )
    request = make_request()
    evidence = [make_evidence()]
    config = make_config()

    monkeypatch.setattr("app.agents.llm.load_prompt", lambda name: "prompt v1")
    analyze_fundamentals_llm(provider, request, evidence, config)
    monkeypatch.setattr("app.agents.llm.load_prompt", lambda name: "prompt v2")
    analyze_fundamentals_llm(provider, request, evidence, config)

    assert len(calls) == 2


def test_llm_node_rejects_invalid_claim_type() -> None:
    provider = make_provider(
        lambda _prompt, _config: {
            "claims": [
                make_claim_payload(claim_type="risk", risk_severity="medium")
            ]
        }
    )
    request = make_request()
    evidence = [make_evidence()]
    config = make_config()

    with pytest.raises(ModelProviderError, match="E301.*fundamental"):
        analyze_fundamentals_llm(provider, request, evidence, config)


def test_risk_llm_rejects_non_review_status() -> None:
    provider = make_provider(
        lambda _prompt, _config: {
            "claims": [
                make_claim_payload(
                    claim_id="CL-LLM-RISK",
                    claim_type="risk",
                    risk_severity="medium",
                    status="pass",
                    evidence_ids=["EV-FOOD-001"],
                )
            ]
        }
    )
    request = make_request()
    evidence = [make_evidence()]
    config = make_config()

    with pytest.raises(ModelProviderError, match="E301.*risk node"):
        analyze_risks_llm(provider, request, evidence, config)


def test_run_analysis_uses_llm_when_provider_injected() -> None:
    calls: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        calls.append(prompt)
        if "新闻与政策分析提示词" in prompt:
            return {"claims": [make_claim_payload(claim_type="change", status="review")]}
        if "风险分析提示词" in prompt:
            return {
                "claims": [
                    make_claim_payload(
                        claim_id="CL-LLM-RISK",
                        claim_type="risk",
                        risk_severity="medium",
                        status="review",
                        evidence_ids=["EV-FOOD-001"],
                    )
                ]
            }
        return {"claims": [make_claim_payload()]}

    provider = make_provider(transport)
    request = make_request()
    evidence = [make_evidence()]
    config = make_config()
    documents = [make_document()]

    claims = run_analysis(
        request,
        evidence,
        config,
        documents=documents,
        provider=provider,
    )

    assert len(claims) == 3
    assert len(calls) == 3
    assert all(isinstance(claim, Claim) for claim in claims)


def test_run_critic_llm_returns_issues() -> None:
    captured: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        captured.append(prompt)
        return {"issues": [make_issue_payload()]}

    provider = make_provider(transport)
    request = make_request()
    evidence = [make_evidence()]
    config = make_config()
    claim = Claim.model_validate(make_claim_payload())

    issues = run_critic_llm(provider, request, [claim], evidence, config)

    assert len(issues) == 1
    assert isinstance(issues[0], ValidationIssue)
    assert issues[0].issue_id == "ISSUE-LLM-001"
    assert "行业 Critic 提示词" in captured[0]


def test_prompt_versions_are_loaded() -> None:
    versions = get_prompt_versions()

    assert set(versions) == {
        "fundamental",
        "news_policy",
        "risk",
        "critic_industry",
    }
    assert all(version == "1" for version in versions.values())
