"""Contract tests for the shared public schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import (
    Claim,
    Evidence,
    IndustryConfig,
    ResearchReport,
    ResearchRequest,
    RunMetadata,
    SourceDocument,
    TextChunk,
    ValidationIssue,
)


ROOT = Path(__file__).parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "shared"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_all_public_schemas_are_importable_and_fixtures_validate() -> None:
    request = ResearchRequest.model_validate(load_fixture("research_request.json"))
    document = SourceDocument.model_validate(load_fixture("source_document.json"))
    evidence = Evidence.model_validate(load_fixture("evidence.json"))
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    report = ResearchReport.model_validate(load_fixture("report.json"))

    chunk = TextChunk(
        chunk_id="CHUNK-FOOD-001",
        doc_id=document.doc_id,
        text="本期营业收入同比增长 12.0%。",
        page=42,
        section="经营情况讨论与分析",
        paragraph_index=0,
        char_start=0,
        char_end=18,
    )
    claim = Claim(
        claim_id="CL-FOOD-001",
        text="报告披露本期营业收入同比增长 12.0%。",
        claim_type="fact",
        evidence_ids=[evidence.evidence_id],
        calculation=None,
        confidence=0.95,
        industry_metric_ids=[config.required_metrics[0].metric_id],
        status="pass",
    )
    issue = ValidationIssue(
        issue_id="ISSUE-FOOD-001",
        check_name="required_metric_coverage",
        severity="warning",
        issue_type="missing_metric",
        message="渠道库存证据仍需人工确认。",
        claim_id=None,
        evidence_id=None,
        report_section="risks",
        rerun_required=False,
        human_confirmation_required=True,
        status="open",
    )
    metadata = RunMetadata(
        run_id=request.run_id,
        started_at="2026-08-24T09:55:00+08:00",
        finished_at="2026-08-24T10:00:00+08:00",
        status="success",
        model_provider="fixture",
        model_name="schema-test",
        prompt_versions={"default": "v1"},
        input_hashes={"manifest": "sha256:fixture"},
        module_versions={"schemas": "v1"},
        errors=[],
    )

    assert request.run_id == "RUN-DEMO"
    assert document.doc_id.startswith("DOC-")
    assert chunk.doc_id == document.doc_id
    assert evidence.chunk_id == chunk.chunk_id
    assert claim.evidence_ids == [evidence.evidence_id]
    assert issue.status == "open"
    assert report.run_id == metadata.run_id


def test_request_rejects_invalid_comparison_range_and_output_dir() -> None:
    payload = load_fixture("research_request.json")
    payload["comparison_start"] = "2026-01-01"
    payload["comparison_end"] = "2025-01-01"
    with pytest.raises(ValidationError, match="comparison_start"):
        ResearchRequest.model_validate(payload)

    payload = load_fixture("research_request.json")
    payload["output_dir"] = "tmp/reports/RUN-DEMO"
    with pytest.raises(ValidationError, match="output_dir"):
        ResearchRequest.model_validate(payload)


def test_schema_constraints_reject_invalid_ids_and_values() -> None:
    with pytest.raises(ValidationError):
        TextChunk(
            chunk_id="BAD-CHUNK",
            doc_id="DOC-FOOD-001",
            text="内容",
        )

    with pytest.raises(ValidationError):
        Evidence.model_validate(
            {**load_fixture("evidence.json"), "confidence": 1.1}
        )

    with pytest.raises(ValidationError, match="require evidence_ids"):
        Claim(
            claim_id="CL-FOOD-INVALID",
            text="无证据结论",
            claim_type="analysis",
            evidence_ids=[],
            calculation=None,
            confidence=0.2,
            industry_metric_ids=[],
            status="draft",
        )

    with pytest.raises(ValidationError):
        TextChunk(
            chunk_id="CHUNK-FOOD-EMPTY",
            doc_id="DOC-FOOD-001",
            text="",
        )


def test_industry_metric_ids_must_be_unique() -> None:
    payload = load_fixture("food_config.json")
    payload["required_metrics"].append(payload["required_metrics"][0])
    with pytest.raises(ValidationError, match="metric_id must be unique"):
        IndustryConfig.model_validate(payload)


def test_extra_public_fields_are_rejected() -> None:
    payload = load_fixture("evidence.json")
    payload["invented_field"] = "must not silently pass"
    with pytest.raises(ValidationError):
        Evidence.model_validate(payload)


def test_evidence_rejects_invalid_evidence_type() -> None:
    payload = load_fixture("evidence.json")
    payload["evidence_type"] = "bogus"
    with pytest.raises(ValidationError):
        Evidence.model_validate(payload)


def test_industry_config_rejects_invalid_metric_evidence_types() -> None:
    payload = load_fixture("food_config.json")
    payload["required_metrics"][0]["evidence_types"] = ["bogus"]
    with pytest.raises(ValidationError):
        IndustryConfig.model_validate(payload)


def test_industry_config_rejects_invalid_risk_evidence_types() -> None:
    payload = load_fixture("food_config.json")
    payload["risk_rules"][0]["required_evidence_types"] = ["bogus"]
    with pytest.raises(ValidationError):
        IndustryConfig.model_validate(payload)


def test_industry_config_rejects_empty_trigger_terms() -> None:
    payload = load_fixture("food_config.json")
    payload["risk_rules"][0]["trigger_terms"] = []
    with pytest.raises(ValidationError):
        IndustryConfig.model_validate(payload)


def test_industry_config_rejects_blank_trigger_terms() -> None:
    payload = load_fixture("food_config.json")
    payload["risk_rules"][0]["trigger_terms"] = ["   "]
    with pytest.raises(ValidationError):
        IndustryConfig.model_validate(payload)


def test_industry_config_rejects_empty_keywords() -> None:
    payload = load_fixture("food_config.json")
    payload["required_metrics"][0]["keywords"] = []
    with pytest.raises(ValidationError):
        IndustryConfig.model_validate(payload)


def test_industry_config_rejects_blank_keywords() -> None:
    payload = load_fixture("food_config.json")
    payload["required_metrics"][0]["keywords"] = ["   "]
    with pytest.raises(ValidationError):
        IndustryConfig.model_validate(payload)


def test_contract_change_006_inventory_metric_semantics() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    metrics = {metric.metric_id: metric for metric in config.required_metrics}

    inventory = metrics["inventory"]
    assert "库存" not in inventory.keywords
    assert "动销" not in inventory.keywords
    assert inventory.evidence_types == ["financial"]
    assert inventory.evidence_requirement == "single"

    volume = metrics["inventory_volume"]
    assert volume.required is False
    assert volume.evidence_types == ["operating"]
    assert volume.evidence_requirement == "single"
    assert "库存量" in volume.keywords
    assert "期末库存量" in volume.keywords
    assert "产成品库存量" in volume.keywords
    assert "动销" not in volume.keywords
    assert "渠道库存" not in volume.keywords
    assert "经销商库存" not in volume.keywords

    channel = metrics["channel"]
    assert channel.required is False
    assert channel.evidence_types == ["operating", "company_release", "news"]
    assert channel.evidence_requirement == "single"
    assert "动销" in channel.keywords
    assert "渠道库存" in channel.keywords
    assert "经销商库存" in channel.keywords


def test_contract_change_006_retrieval_keywords_include_new_metric_entries() -> None:
    config = IndustryConfig.model_validate(load_fixture("food_config.json"))
    retrieval = config.retrieval_keywords

    assert "库存" not in retrieval
    assert "库存量" in retrieval
    assert "渠道库存" in retrieval
    assert "经销商库存" in retrieval
    assert "动销" in retrieval


def test_risk_claim_requires_severity() -> None:
    with pytest.raises(ValidationError, match="risk_severity"):
        Claim(
            claim_id="CL-RISK-MISSING-SEVERITY",
            text="风险结论。",
            claim_type="risk",
            evidence_ids=["EV-FOOD-001"],
            calculation=None,
            confidence=0.5,
            industry_metric_ids=["inventory"],
            status="review",
        )


def test_risk_rule_metric_ids_must_reference_known_metrics() -> None:
    payload = load_fixture("food_config.json")
    payload["risk_rules"][0]["metric_ids"] = ["missing_metric"]
    with pytest.raises(ValidationError, match="unknown metric_ids"):
        IndustryConfig.model_validate(payload)


def test_risk_ids_must_be_unique() -> None:
    payload = load_fixture("food_config.json")
    payload["risk_rules"].append(dict(payload["risk_rules"][0]))
    with pytest.raises(ValidationError, match="risk_id must be unique"):
        IndustryConfig.model_validate(payload)

