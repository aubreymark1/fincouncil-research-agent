"""Tests for the compact, single-call LLM workbench path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.aggregation import run_analysis
from app.agents.compact import (
    run_compact_analysis,
    run_compact_report,
    select_compact_evidence,
)
from app.model import ModelConfig, ModelProvider, ModelProviderError
from app.orchestrator.graph import run_pipeline
from app.schemas import (
    Evidence,
    IndustryConfig,
    ResearchRequest,
    ReportBlock,
    SourceDocument,
    TextChunk,
)


ROOT = Path(__file__).parents[2]


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "shared" / name).read_text(encoding="utf-8"))


def make_request(**updates: object) -> ResearchRequest:
    payload = {**load_fixture("research_request.json"), **updates}
    return ResearchRequest.model_validate(payload)


def make_config() -> IndustryConfig:
    return IndustryConfig.model_validate(load_fixture("food_config.json"))


def make_document() -> SourceDocument:
    return SourceDocument.model_validate(load_fixture("source_document.json"))


def make_evidence(
    evidence_id: str,
    *,
    fact_text: str = "营业收入同比增长 12%。",
    evidence_type: str = "financial",
    review_status: str = "verified",
    industry_id: str | None = "food_beverage",
    confidence: float = 0.9,
) -> Evidence:
    payload = {
        **load_fixture("evidence.json"),
        "evidence_id": evidence_id,
        "chunk_id": f"CHUNK-{evidence_id.removeprefix('EV-')}",
        "fact_text": fact_text,
        "quote": fact_text,
        "evidence_type": evidence_type,
        "review_status": review_status,
        "industry_id": industry_id,
        "confidence": confidence,
    }
    return Evidence.model_validate(payload)


def make_claim(evidence_ids: list[str]) -> dict:
    return {
        "claim_id": "CL-COMPACT-001",
        "text": "营业收入同比增长 12%。",
        "claim_type": "change",
        "risk_severity": None,
        "evidence_ids": evidence_ids,
        "calculation": None,
        "confidence": 0.8,
        "industry_metric_ids": ["revenue_growth"],
        "status": "pass",
    }


def test_selector_filters_scope_and_obeys_global_limit() -> None:
    config = make_config()
    evidence = [
        make_evidence("EV-REV-001", fact_text="营业收入增长 12%。"),
        make_evidence("EV-REV-002", fact_text="营业收入增长 10%。"),
        make_evidence("EV-REV-003", fact_text="营业收入增长 8%。"),
        make_evidence("EV-PENDING", review_status="pending"),
        make_evidence("EV-BANK", industry_id="banking"),
    ]

    selected = select_compact_evidence(
        evidence,
        config,
        max_total=2,
        per_metric=3,
    )

    assert len(selected) == 2
    assert {item.evidence_id for item in selected} <= {
        "EV-REV-001",
        "EV-REV-002",
        "EV-REV-003",
    }


def test_selector_keeps_risk_trigger_and_exclude_signals() -> None:
    config = make_config()
    evidence = [
        make_evidence(
            "EV-RISK-TRIGGER",
            fact_text="存货增速高于收入增速。",
            evidence_type="financial",
        ),
        make_evidence(
            "EV-RISK-EXCLUDE",
            fact_text="库存压力已缓解。",
            evidence_type="operating",
        ),
    ]

    selected = select_compact_evidence(
        evidence,
        config,
        max_total=10,
        per_risk=2,
    )

    selected_ids = {item.evidence_id for item in selected}
    assert {"EV-RISK-TRIGGER", "EV-RISK-EXCLUDE"} <= selected_ids


def test_selector_default_budget_stays_small_for_the_online_mvp() -> None:
    config = make_config()
    evidence = [
        make_evidence(
            f"EV-BUDGET-{index:03d}",
            fact_text=f"营业收入增长 {index}%。",
        )
        for index in range(40)
    ]

    selected = select_compact_evidence(evidence, config)

    assert len(selected) <= 24


def test_compact_analysis_uses_one_call_and_accepts_bare_claim_array() -> None:
    calls: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> list[dict]:
        calls.append(prompt)
        return [make_claim(["EV-COMPACT-001"])]

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    claims = run_compact_analysis(
        provider,
        make_request(),
        [make_evidence("EV-COMPACT-001")],
        make_config(),
        documents=[make_document()],
    )

    assert len(calls) == 1
    assert len(claims) == 1
    assert "轻量综合分析" in calls[0]
    assert "最多输出 4 个段落" in calls[0]
    assert "事实—变化—影响" in calls[0]


def test_compact_analysis_rejects_unknown_evidence_id() -> None:
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: {"claims": [make_claim(["EV-NOT-SENT"])]},
    )

    with pytest.raises(ModelProviderError, match="unknown evidence IDs"):
        run_compact_analysis(
            provider,
            make_request(),
            [make_evidence("EV-COMPACT-001")],
            make_config(),
            documents=[make_document()],
        )


def test_compact_report_returns_narrative_blocks_with_sources() -> None:
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: {
            "narrative": [
                {
                    "section": "核心判断",
                    "text": "行业收入出现分化，需关注需求变化。",
                    "evidence_ids": ["EV-COMPACT-001"],
                }
            ],
            "claims": [make_claim(["EV-COMPACT-001"])],
        },
    )

    draft = run_compact_report(
        provider,
        make_request(),
        [make_evidence("EV-COMPACT-001")],
        make_config(),
        documents=[make_document()],
    )

    assert draft.narrative == [
        ReportBlock(
            section="核心判断",
            text="行业收入出现分化，需关注需求变化。",
            evidence_ids=["EV-COMPACT-001"],
        )
    ]


def test_compact_report_accepts_narrative_only_llm_output() -> None:
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: {
            "narrative": [
                {
                    "section": "核心判断",
                    "text": "行业需求保持韧性，但增长动能出现分化。",
                    "evidence_ids": ["EV-COMPACT-001"],
                }
            ]
        },
    )

    draft = run_compact_report(
        provider,
        make_request(),
        [make_evidence("EV-COMPACT-001")],
        make_config(),
        documents=[make_document()],
    )

    assert draft.claims == []
    assert draft.narrative[0].text.startswith("行业需求保持韧性")


def test_compact_report_keeps_text_and_filters_unknown_narrative_sources() -> None:
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: {
            "narrative": [
                {
                    "section": "核心判断",
                    "text": "行业需求保持韧性。",
                    "evidence_ids": ["EV-COMPACT-001", "EV-MODEL-INVENTED"],
                }
            ]
        },
    )

    draft = run_compact_report(
        provider,
        make_request(),
        [make_evidence("EV-COMPACT-001")],
        make_config(),
        documents=[make_document()],
    )

    assert draft.narrative[0].evidence_ids == ["EV-COMPACT-001"]


def test_compact_report_builds_narrative_when_model_returns_claims_only() -> None:
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: {
            "claims": [make_claim(["EV-COMPACT-001"])],
        },
    )

    draft = run_compact_report(
        provider,
        make_request(),
        [make_evidence("EV-COMPACT-001")],
        make_config(),
        documents=[make_document()],
    )

    assert draft.narrative
    assert draft.narrative[0].section == "核心判断"
    assert draft.narrative[0].text == "营业收入同比增长 12%。"
    assert draft.narrative[0].evidence_ids == ["EV-COMPACT-001"]


def test_run_analysis_compact_strategy_calls_provider_once() -> None:
    calls: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        calls.append(prompt)
        return {"claims": [make_claim(["EV-COMPACT-001"])]}

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    claims = run_analysis(
        make_request(),
        [make_evidence("EV-COMPACT-001")],
        make_config(),
        documents=[make_document()],
        provider=provider,
        llm_strategy="compact",
    )

    assert len(calls) == 1
    assert claims[0].claim_id == "CL-COMPACT-001"


def test_run_pipeline_compact_skips_llm_critic() -> None:
    calls: list[str] = []

    def transport(prompt: str, _config: ModelConfig) -> dict:
        calls.append(prompt)
        return {"claims": []}

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)
    request = make_request(run_id="RUN-COMPACT-PIPELINE")
    document = make_document()

    state = run_pipeline(
        request,
        manifest_loader=lambda _path: [document],
        text_extractor=lambda _document: [
            TextChunk(
                chunk_id="CHUNK-FOOD-001-COMPACT",
                doc_id=document.doc_id,
                text="本期营业收入同比增长 12%。",
                page=42,
                section="经营情况讨论与分析",
                paragraph_index=1,
                char_start=0,
                char_end=15,
            )
        ],
        industry_loader=load_config_for_test,
        model_provider=provider,
        llm_strategy="compact",
    )

    assert len(calls) == 1
    assert state.metadata is not None
    assert state.metadata.prompt_versions == {"synthesis": "3"}


def load_config_for_test(industry_id: str) -> IndustryConfig:
    assert industry_id == "food_beverage"
    return make_config()
