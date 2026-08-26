"""Tests for C-002 industry checklist and required-metric coverage."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.industry import (
    build_industry_checklist,
    check_required_metrics,
    load_industry_config,
)
from app.schemas import Evidence, IndustryConfig, MetricRule, SourceDocument


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


def make_config(*metrics: MetricRule) -> IndustryConfig:
    return IndustryConfig(
        industry_id="food_beverage",
        display_name="测试食品饮料",
        required_metrics=list(metrics),
        event_taxonomy=["业绩"],
        risk_rules=[],
        report_sections=["summary"],
        retrieval_keywords=["收入"],
    )


def make_document(
    doc_id: str,
    publisher: str = "公司A",
    content_hash: str = "hashA",
    published_at: date = date(2026, 1, 1),
    company_name: str = "测试公司",
    industry_id: str = "food_beverage",
) -> SourceDocument:
    return SourceDocument(
        doc_id=f"DOC-{doc_id}",
        title=f"文档{doc_id}",
        source_type="annual_report",
        publisher=publisher,
        source_url=None,
        local_path=f"data/{doc_id}.pdf",
        published_at=published_at,
        event_date=None,
        retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        company_name=company_name,
        industry_id=industry_id,
        trust_level=3,
        content_hash=content_hash,
        review_status="formal",
    )


def make_evidence(
    evidence_id: str = "E1",
    doc_id: str = "A",
    text: str = "本期营业收入同比增长 12%。",
    evidence_type: str = "financial",
    review_status: str = "verified",
    industry_id: str = "food_beverage",
    published_at: date = date(2026, 1, 1),
    company_name: str = "测试公司",
) -> Evidence:
    return Evidence(
        evidence_id=f"EV-{evidence_id}",
        doc_id=f"DOC-{doc_id}",
        chunk_id=f"CHUNK-{doc_id}-001",
        fact_text=text,
        quote=text,
        published_at=published_at,
        page=1,
        section="经营情况讨论与分析",
        locator=f"page 1, doc {doc_id}",
        company_name=company_name,
        industry_id=industry_id,
        evidence_type=evidence_type,
        confidence=0.5,
        review_status=review_status,  # type: ignore[arg-type]
    )


def test_build_checklist_food_beverage_requires_inventory() -> None:
    config = load_industry_config("food_beverage")
    checklist = build_industry_checklist(config)

    assert "inventory" in checklist
    assert "net_interest_margin" not in checklist


def test_build_checklist_banking_requires_net_interest_margin() -> None:
    config = load_industry_config("banking")
    checklist = build_industry_checklist(config)

    assert "net_interest_margin" in checklist
    assert "inventory" not in checklist


def test_build_checklist_excludes_optional_metrics() -> None:
    config = make_config(
        make_metric(required=True),
        make_metric(metric_id="volume", display_name="销量", required=False),
    )

    assert build_industry_checklist(config) == ["revenue_growth"]


def test_missing_required_metric_returns_e202() -> None:
    config = make_config(make_metric(required=True, missing_action="review"))

    issues = check_required_metrics([], config, documents=[])

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"
    assert "E202" in issues[0].message
    assert issues[0].severity == "error"


def test_optional_metric_missing_does_not_produce_issue() -> None:
    config = make_config(
        make_metric(required=True),
        make_metric(metric_id="volume", display_name="销量", required=False),
    )

    issues = check_required_metrics([], config, documents=[])

    assert len(issues) == 1
    assert "volume" not in issues[0].message


def test_single_evidence_requirement_is_satisfied() -> None:
    config = make_config(make_metric(required=True, evidence_requirement="single"))
    evidence = [make_evidence()]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert issues == []


def test_single_evidence_without_source_document_does_not_count() -> None:
    config = make_config(make_metric(required=True, evidence_requirement="single"))
    evidence = [make_evidence()]

    issues = check_required_metrics(evidence, config, documents=[])

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_mixed_source_traced_and_untraced_evidence_counts_only_traced() -> None:
    config = make_config(make_metric(required=True, evidence_requirement="single"))
    documents = [make_document("A")]
    evidence = [
        make_evidence("E1", doc_id="A", text="营业收入增长 12%。"),
        make_evidence("E2", doc_id="B", text="营业收入增长 8%。"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert issues == []


def test_keyword_mismatch_does_not_count() -> None:
    config = make_config(make_metric(required=True))
    evidence = [make_evidence(text="净利润同比增长 5%。")]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_pending_evidence_does_not_count() -> None:
    config = make_config(make_metric(required=True))
    evidence = [make_evidence(review_status="pending")]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_invalid_evidence_type_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        make_evidence(evidence_type="keyword_match")


def test_wrong_industry_evidence_does_not_count() -> None:
    config = make_config(make_metric(required=True))
    evidence = [make_evidence(industry_id="banking")]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_metric_specific_evidence_type_mismatch_does_not_count() -> None:
    config = make_config(make_metric(required=True))
    evidence = [make_evidence(evidence_type="policy")]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_metric_evidence_types_are_config_driven() -> None:
    config = make_config(
        make_metric(metric_id="custom_growth", evidence_types=["policy"])
    )
    evidence = [make_evidence(evidence_type="policy")]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert issues == []


def test_metric_evidence_types_do_not_fallback_to_all() -> None:
    config = make_config(
        make_metric(metric_id="custom_growth", evidence_types=["financial"])
    )
    evidence = [make_evidence(evidence_type="policy")]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_evidence_industry_must_match_source_document() -> None:
    config = make_config(make_metric())
    documents = [make_document("A", industry_id="banking")]
    evidence = [make_evidence(industry_id="food_beverage")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_evidence_published_at_must_match_source_document() -> None:
    config = make_config(make_metric())
    documents = [make_document("A", published_at=date(2026, 1, 1))]
    evidence = [make_evidence(published_at=date(2026, 2, 1))]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_evidence_company_name_must_match_source_document() -> None:
    config = make_config(make_metric())
    documents = [make_document("A", company_name="测试公司")]
    evidence = [make_evidence(company_name="另一公司")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "missing_metric"


def test_empty_keywords_are_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        make_metric(keywords=[])


def test_blank_keywords_are_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        make_metric(keywords=["   "])


def test_duplicate_and_whitespace_keywords_are_normalized() -> None:
    config = make_config(
        make_metric(keywords=["收入", " 收入 ", "收入"])
    )
    evidence = [make_evidence()]
    documents = [make_document("A")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert issues == []


def test_special_metric_id_produces_valid_issue_id() -> None:
    import re

    config = make_config(
        make_metric(metric_id="收入 增速/同比", display_name="特殊指标")
    )

    issues = check_required_metrics([], config, documents=[])

    assert len(issues) == 1
    assert re.fullmatch(r"ISSUE-[A-Za-z0-9][A-Za-z0-9._-]*", issues[0].issue_id) is not None


@pytest.mark.parametrize(
    "publisher_b",
    [" 公司A ", "公司a"],
)
def test_publisher_normalization_prevents_false_independence(
    publisher_b: str,
) -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="存货",
            keywords=["存货"],
            required=True,
            evidence_requirement="multiple",
        )
    )
    documents = [
        make_document("A", publisher="公司A", content_hash="hashA"),
        make_document("B", publisher=publisher_b, content_hash="hashB"),
    ]
    evidence = [
        make_evidence("E1", doc_id="A", text="存货余额同比增长。", evidence_type="financial"),
        make_evidence("E2", doc_id="B", text="存货周转天数上升。", evidence_type="financial"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "insufficient_evidence"


def test_multiple_requirement_rejects_same_document_sources() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="存货",
            keywords=["存货"],
            required=True,
            evidence_requirement="multiple",
        )
    )
    documents = [make_document("A", publisher="公司A", content_hash="hashA")]
    evidence = [
        make_evidence("E1", doc_id="A", text="存货余额同比增长。", evidence_type="financial"),
        make_evidence("E2", doc_id="A", text="存货周转天数上升。", evidence_type="financial"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "insufficient_evidence"


def test_multiple_requirement_rejects_same_publisher() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="存货",
            keywords=["存货"],
            required=True,
            evidence_requirement="multiple",
        )
    )
    documents = [
        make_document("A", publisher="公司A", content_hash="hashA"),
        make_document("B", publisher="公司A", content_hash="hashB"),
    ]
    evidence = [
        make_evidence("E1", doc_id="A", text="存货余额同比增长。", evidence_type="financial"),
        make_evidence("E2", doc_id="B", text="存货周转天数上升。", evidence_type="financial"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "insufficient_evidence"


def test_multiple_requirement_rejects_same_content_hash() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="存货",
            keywords=["存货"],
            required=True,
            evidence_requirement="multiple",
        )
    )
    documents = [
        make_document("A", publisher="公司A", content_hash="hashA"),
        make_document("B", publisher="公司B", content_hash="hashA"),
    ]
    evidence = [
        make_evidence("E1", doc_id="A", text="存货余额同比增长。", evidence_type="financial"),
        make_evidence("E2", doc_id="B", text="存货周转天数上升。", evidence_type="financial"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "insufficient_evidence"


def test_multiple_requirement_independent_sources_pass() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="存货",
            keywords=["存货"],
            required=True,
            evidence_requirement="multiple",
        )
    )
    documents = [
        make_document("A", publisher="公司A", content_hash="hashA"),
        make_document("B", publisher="公司B", content_hash="hashB"),
    ]
    evidence = [
        make_evidence("E1", doc_id="A", text="存货余额同比增长。", evidence_type="financial"),
        make_evidence("E2", doc_id="B", text="存货周转天数上升。", evidence_type="financial"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert issues == []


def test_multiple_requirement_missing_document_does_not_count() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="存货",
            keywords=["存货"],
            required=True,
            evidence_requirement="multiple",
        )
    )
    documents = [make_document("A", publisher="公司A", content_hash="hashA")]
    evidence = [
        make_evidence("E1", doc_id="A", text="存货余额同比增长。", evidence_type="financial"),
        make_evidence("E2", doc_id="B", text="存货周转天数上升。", evidence_type="financial"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert issues[0].issue_type == "insufficient_evidence"


@pytest.mark.parametrize(
    ("missing_action", "expected_severity"),
    [
        ("warn", "warning"),
        ("review", "error"),
        ("reject", "critical"),
    ],
)
def test_missing_action_severity_mapping(
    missing_action: str,
    expected_severity: str,
) -> None:
    config = make_config(make_metric(required=True, missing_action=missing_action))

    issues = check_required_metrics([], config, documents=[])

    assert len(issues) == 1
    assert issues[0].severity == expected_severity


def test_food_config_inventory_semantics() -> None:
    config = load_industry_config("food_beverage")
    metric_by_id = {metric.metric_id: metric for metric in config.required_metrics}

    inventory = metric_by_id["inventory"]
    assert inventory.evidence_types == ["financial"]
    assert inventory.evidence_requirement == "single"
    assert "库存" not in inventory.keywords

    inventory_volume = metric_by_id["inventory_volume"]
    assert inventory_volume.required is False
    assert inventory_volume.evidence_types == ["operating"]
    assert "库存量" in inventory_volume.keywords
    assert "期末库存量" in inventory_volume.keywords
    assert "产成品库存量" in inventory_volume.keywords

    channel = metric_by_id["channel"]
    assert set(channel.evidence_types) == {"operating", "company_release", "news"}
    assert "渠道库存" in channel.keywords
    assert "经销商库存" in channel.keywords
    assert "动销" in channel.keywords

    assert "库存" not in config.retrieval_keywords
    assert "库存量" in config.retrieval_keywords
    assert "渠道库存" in config.retrieval_keywords
    assert "经销商库存" in config.retrieval_keywords


def test_inventory_stock_does_not_match_inventory_or_inventory_volume() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="财务存货",
            keywords=["存货"],
            evidence_types=["financial"],
            required=True,
        ),
        make_metric(
            metric_id="inventory_volume",
            display_name="实物库存量",
            keywords=["库存量"],
            evidence_types=["operating"],
            required=True,
        ),
    )
    documents = [make_document("A")]
    evidence = [
        make_evidence("E1", text="库存股数量没有变化。", evidence_type="financial"),
        make_evidence("E2", text="库存股数量没有变化。", evidence_type="operating"),
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 2
    assert all("库存股" not in issue.message for issue in issues)


def test_inventory_volume_only_matches_volume_evidence() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="财务存货",
            keywords=["存货"],
            evidence_types=["financial"],
            required=True,
        ),
        make_metric(
            metric_id="inventory_volume",
            display_name="实物库存量",
            keywords=["库存量"],
            evidence_types=["operating"],
            required=True,
        ),
    )
    documents = [make_document("A")]
    evidence = [make_evidence("E1", text="期末库存量100吨。", evidence_type="operating")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert "inventory_volume" not in issues[0].message
    assert "inventory (" in issues[0].message or "财务存货" in issues[0].message


def test_inventory_financial_only_matches_inventory() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="财务存货",
            keywords=["存货"],
            evidence_types=["financial"],
            required=True,
        ),
        make_metric(
            metric_id="inventory_volume",
            display_name="实物库存量",
            keywords=["库存量"],
            evidence_types=["operating"],
            required=True,
        ),
    )
    documents = [make_document("A")]
    evidence = [make_evidence("E1", text="存货614亿元。", evidence_type="financial")]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 1
    assert "inventory_volume" in issues[0].message


def test_channel_keywords_only_match_channel() -> None:
    config = make_config(
        make_metric(
            metric_id="inventory",
            display_name="财务存货",
            keywords=["存货"],
            evidence_types=["financial"],
            required=True,
        ),
        make_metric(
            metric_id="inventory_volume",
            display_name="实物库存量",
            keywords=["库存量"],
            evidence_types=["operating"],
            required=True,
        ),
        make_metric(
            metric_id="channel",
            display_name="渠道库存与动销",
            keywords=["渠道库存", "经销商库存", "动销"],
            evidence_types=["operating", "company_release", "news"],
            required=True,
        ),
    )
    documents = [make_document("A")]
    evidence = [
        make_evidence("E1", text="渠道库存高企，动销放缓。", evidence_type="operating")
    ]

    issues = check_required_metrics(evidence, config, documents=documents)

    assert len(issues) == 2
    assert all("channel" not in issue.message for issue in issues)


def test_banking_config_does_not_add_food_inventory_metrics() -> None:
    config = load_industry_config("banking")
    metric_ids = {metric.metric_id for metric in config.required_metrics}

    assert not (metric_ids & {"inventory", "inventory_volume", "channel"})
