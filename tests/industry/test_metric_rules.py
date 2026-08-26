"""Tests for C-004 industry metric-level rules (ValidationIssue output)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.industry import apply_metric_rules, load_industry_config
from app.schemas import (
    Evidence,
    IndustryConfig,
    MetricRule,
    RiskRule,
    SourceDocument,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# Fixture builders (mirror the style of test_checklist.py / test_risk_rules.py).
# ---------------------------------------------------------------------------


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
    trigger_description: str = "库存变化需要结合收入证据判断。",
    trigger_terms: list[str] | None = None,
    exclude_terms: list[str] | None = None,
    metric_ids: list[str] | None = None,
    required_evidence_types: list[str] | None = None,
    severity: str = "medium",
) -> RiskRule:
    return RiskRule(
        risk_id=risk_id,
        display_name=display_name,
        trigger_description=trigger_description,
        trigger_terms=trigger_terms
        or ["存货增速高于收入增速", "库存压力", "库存积压", "库存高企"],
        exclude_terms=exclude_terms if exclude_terms is not None else [],
        metric_ids=metric_ids or ["inventory", "revenue_growth"],
        required_evidence_types=required_evidence_types or ["financial"],
        severity=severity,  # type: ignore[arg-type]
    )


def make_food_config(*metrics: MetricRule, risk_rules: list[RiskRule] | None = None) -> IndustryConfig:
    if not metrics:
        metrics = (
            make_metric(
                metric_id="revenue_growth",
                display_name="收入增速",
                keywords=["营业收入", "收入增长", "收入增速", "营收"],
            ),
            make_metric(
                metric_id="gross_margin",
                display_name="毛利率",
                keywords=["毛利率", "毛利", "营业成本"],
            ),
            make_metric(
                metric_id="inventory",
                display_name="财务存货",
                keywords=["存货", "存货余额"],
            ),
        )
    return IndustryConfig(
        industry_id="food_beverage",
        display_name="测试食品饮料",
        required_metrics=list(metrics),
        event_taxonomy=["业绩"],
        risk_rules=risk_rules if risk_rules is not None else [make_risk_rule()],
        report_sections=["summary", "risks"],
        retrieval_keywords=["收入", "存货", "毛利率"],
    )


def make_bank_config(*metrics: MetricRule, risk_rules: list[RiskRule] | None = None) -> IndustryConfig:
    if not metrics:
        metrics = (
            make_metric(
                metric_id="net_interest_margin",
                display_name="净息差",
                keywords=["净息差", "净利息收益率", "息差"],
            ),
            make_metric(
                metric_id="non_performing_loan_ratio",
                display_name="不良贷款率",
                keywords=["不良率", "不良贷款率"],
            ),
            make_metric(
                metric_id="provision_coverage",
                display_name="拨备覆盖率",
                keywords=["拨备覆盖率", "拨备"],
            ),
            make_metric(
                metric_id="capital_adequacy",
                display_name="资本充足率",
                keywords=["资本充足率", "核心一级资本充足率", "一级资本充足率"],
            ),
            make_metric(
                metric_id="real_estate_exposure",
                display_name="房地产风险敞口",
                keywords=["房地产贷款", "房地产风险", "开发贷", "按揭贷款"],
                evidence_types=["financial", "news", "policy"],
                required=False,
            ),
        )
    return IndustryConfig(
        industry_id="banking",
        display_name="测试银行",
        required_metrics=list(metrics),
        event_taxonomy=["业绩", "信贷风险"],
        risk_rules=risk_rules if risk_rules is not None else [
            make_risk_rule(
                risk_id="credit_risk_deterioration",
                display_name="信用风险恶化",
                trigger_description="不良率和拨备覆盖率需联合检查。",
                trigger_terms=["不良率上升", "拨备覆盖率下降"],
                metric_ids=["non_performing_loan_ratio", "provision_coverage"],
                required_evidence_types=["financial", "policy"],
                severity="high",
            )
        ],
        report_sections=["summary", "credit_risk"],
        retrieval_keywords=["净息差", "不良率", "拨备覆盖率", "资本充足率", "房地产贷款"],
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
        evidence_type=evidence_type,  # type: ignore[arg-type]
        confidence=0.5,
        review_status=review_status,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Shape and dispatch.
# ---------------------------------------------------------------------------


def test_returns_validation_issues_only() -> None:
    config = make_food_config()
    evidence = [make_evidence(text="报告披露存货增速高于收入增速。")]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert all(isinstance(issue, ValidationIssue) for issue in issues)
    assert all(issue.check_name == "metric_rule_check" for issue in issues)
    assert all(issue.issue_id.startswith("ISSUE-C004-") for issue in issues)
    assert all(issue.rerun_required for issue in issues)
    assert all(issue.human_confirmation_required for issue in issues)


def test_empty_evidence_returns_no_issues() -> None:
    assert apply_metric_rules([], make_food_config(), documents=[]) == []
    assert apply_metric_rules([], make_bank_config(), documents=[]) == []


def test_unknown_industry_returns_no_issues() -> None:
    config = IndustryConfig(
        industry_id="pharma",
        display_name="医药",
        required_metrics=[make_metric(metric_id="revenue_growth")],
        event_taxonomy=["业绩"],
        risk_rules=[],
        report_sections=["summary"],
        retrieval_keywords=["收入"],
    )

    assert apply_metric_rules([], config, documents=[]) == []


def test_pending_and_cross_industry_evidence_are_ignored() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="报告披露存货增速高于收入增速。",
            review_status="pending",
        ),
        make_evidence(
            "E2",
            text="报告披露存货增速高于收入增速。",
            industry_id="banking",
        ),
    ]

    assert apply_metric_rules(evidence, config, documents=[]) == []


def test_food_and_banking_rule_sets_differ() -> None:
    """Food and banking must apply different rule sets (industry adaptation)."""

    food = load_industry_config("food_beverage")
    banking = load_industry_config("banking")

    # Same trigger text should not produce identical issue sets across the two
    # industries, because each industry registers different rules.
    food_issues = apply_metric_rules(
        [make_evidence(text="本期毛利率下滑 2 个百分点。", industry_id="food_beverage")],
        food,
        documents=[],
    )
    banking_issues = apply_metric_rules(
        [make_evidence(text="本期毛利率下滑 2 个百分点。", industry_id="banking")],
        banking,
        documents=[],
    )

    food_types = {issue.issue_type for issue in food_issues}
    banking_types = {issue.issue_type for issue in banking_issues}
    assert food_types != banking_types or (not food_types and not banking_types)
    # The food margin-period rule should fire for food but not for banking.
    assert "gross_margin_missing_period" in food_types
    assert "gross_margin_missing_period" not in banking_types


# ---------------------------------------------------------------------------
# Food beverage rules.
# ---------------------------------------------------------------------------


def test_food_inventory_growth_over_revenue_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="报告披露存货增速高于收入增速。",
            evidence_type="financial",
        ),
        make_evidence(
            "E2",
            text="本期营业收入同比增长 12%。",
            evidence_type="financial",
        ),
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert any(i.issue_type == "inventory_growth_over_revenue" for i in issues)


def test_food_inventory_growth_without_revenue_evidence_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期存货增速 20%，显著高于往年。",
            evidence_type="financial",
        ),
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    assert issues[0].issue_type == "inventory_growth_without_revenue"
    assert "revenue_growth" in issues[0].message


def test_food_inventory_change_without_comparison_phrase_not_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期存货余额同比增长 8%。",
            evidence_type="financial",
        ),
        make_evidence(
            "E2",
            text="本期营业收入同比增长 12%。",
            evidence_type="financial",
        ),
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type.startswith("inventory_growth") for i in issues
    )


def test_food_gross_margin_change_without_period_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期毛利率下滑 2 个百分点。",
            evidence_type="financial",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "gross_margin_missing_period"
    assert issue.evidence_id == "EV-E1"
    assert issue.severity == "warning"


def test_food_gross_margin_change_with_period_not_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期毛利率同比下滑 2 个百分点。",
            evidence_type="financial",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type == "gross_margin_missing_period" for i in issues
    )


def test_food_volume_price_substitution_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="按出厂价换算，销量相当于 1.2 亿元。",
            evidence_type="operating",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    assert issues[0].issue_type == "volume_price_substitution"
    assert issues[0].evidence_id == "EV-E1"


def test_food_volume_and_price_without_substitution_not_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期销量同比增长，平均单价保持稳定。",
            evidence_type="operating",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type == "volume_price_substitution" for i in issues
    )


def test_food_management_plan_as_fact_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="公司计划2026年实现营收增长20%，已完成。",
            evidence_type="company_release",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "management_plan_as_fact"
    assert issue.severity == "error"
    assert issue.evidence_id == "EV-E1"


def test_food_management_plan_without_completion_not_flagged() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="公司计划2026年提升产能。",
            evidence_type="company_release",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type == "management_plan_as_fact" for i in issues
    )


# ---------------------------------------------------------------------------
# Banking rules.
# ---------------------------------------------------------------------------


def test_bank_npl_change_without_provision_or_watch_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期不良率上升 5 个基点。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "npl_provision_joint_incomplete"
    assert "拨备覆盖率" in issue.message
    assert "关注类贷款" in issue.message
    assert issue.evidence_id == "EV-E1"


def test_bank_npl_change_with_provision_and_watch_not_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期不良率上升 5 个基点。",
            evidence_type="financial",
            industry_id="banking",
        ),
        make_evidence(
            "E2",
            text="拨备覆盖率下降至 150%，关注类贷款占比稳定。",
            evidence_type="financial",
            industry_id="banking",
        ),
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type == "npl_provision_joint_incomplete" for i in issues
    )


def test_bank_npl_provision_news_does_not_satisfy_joint_check() -> None:
    """Regression for PR #24 inline review: provision-coverage context must
    come from Evidence whose type satisfies the ``provision_coverage`` metric
    (financial). A news-only mention of 拨备 must not satisfy the joint check.
    """

    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期不良率上升 5 个基点。",
            evidence_type="financial",
            industry_id="banking",
        ),
        make_evidence(
            "E2",
            text="拨备覆盖率和关注类贷款均有变化。",
            evidence_type="news",
            industry_id="banking",
        ),
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    npl_issues = [
        i for i in issues if i.issue_type == "npl_provision_joint_incomplete"
    ]
    assert len(npl_issues) == 1
    assert "拨备覆盖率" in npl_issues[0].message
    # 关注类 is mentioned in news and has no dedicated metric, so it is still
    # treated as present at the pool level and should not be reported missing.
    assert "关注类贷款" not in npl_issues[0].message


def test_bank_nim_change_without_period_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期净息差下滑 15 个基点。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    assert issues[0].issue_type == "nim_missing_period"
    assert issues[0].evidence_id == "EV-E1"


def test_bank_nim_change_with_period_not_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期净息差同比下降 15 个基点。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(i.issue_type == "nim_missing_period" for i in issues)


def test_bank_nim_alias_net_interest_yield_flagged() -> None:
    """Regression for PR #24 inline review: the NIM rule must reuse the
    banking config's NIM synonyms (净利息收益率). The config declares
    ``净利息收益率`` as a ``net_interest_margin`` keyword, so the change
    detection must fire for that alias even though the rule's own vocabulary
    only lists bare direction terms.
    """

    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期净利息收益率下降 15 个基点。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "nim_missing_period"
    assert issue.evidence_id == "EV-E1"


def test_bank_capital_adequacy_change_without_caliber_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期资本充足率下降至 12.5%。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    assert issues[0].issue_type == "capital_adequacy_caliber_unverified"
    assert "口径" in issues[0].message
    assert issues[0].evidence_id == "EV-E1"


def test_bank_capital_adequacy_change_with_caliber_not_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="本期核心一级资本充足率下降至 9.5%，口径与上年一致。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type == "capital_adequacy_caliber_unverified" for i in issues
    )


def test_bank_real_estate_news_without_financial_exposure_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="行业新闻报道房地产贷款不良率上升。",
            evidence_type="news",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "real_estate_news_not_bank_specific"
    assert issue.severity == "error"
    assert issue.evidence_id == "EV-E1"


def test_bank_real_estate_news_with_financial_exposure_not_flagged() -> None:
    config = make_bank_config()
    evidence = [
        make_evidence(
            "E1",
            text="行业新闻报道房地产贷款不良率上升。",
            evidence_type="news",
            industry_id="banking",
        ),
        make_evidence(
            "E2",
            text="本行房地产贷款余额 500 亿元。",
            evidence_type="financial",
            industry_id="banking",
        ),
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert not any(
        i.issue_type == "real_estate_news_not_bank_specific" for i in issues
    )


# ---------------------------------------------------------------------------
# Integration with real configs.
# ---------------------------------------------------------------------------


def test_real_food_config_rules_run_without_error() -> None:
    config = load_industry_config("food_beverage")
    evidence = [
        make_evidence(
            "E1",
            text="报告披露存货增速高于收入增速，毛利率下滑。",
            evidence_type="financial",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    issue_types = {issue.issue_type for issue in issues}
    assert "inventory_growth_over_revenue" in issue_types
    assert "gross_margin_missing_period" in issue_types


def test_real_banking_config_rules_run_without_error() -> None:
    config = load_industry_config("banking")
    evidence = [
        make_evidence(
            "E1",
            text="本期不良率上升，净息差下滑，资本充足率下降。",
            evidence_type="financial",
            industry_id="banking",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    issue_types = {issue.issue_type for issue in issues}
    assert "npl_provision_joint_incomplete" in issue_types
    assert "nim_missing_period" in issue_types
    assert "capital_adequacy_caliber_unverified" in issue_types


def test_rules_do_not_emit_stock_price_judgments() -> None:
    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="报告披露存货增速高于收入增速。",
            evidence_type="financial",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    for issue in issues:
        assert "目标价" not in issue.message
        assert "股价" not in issue.message


def test_issue_ids_are_schema_valid() -> None:
    import re

    config = make_food_config()
    evidence = [
        make_evidence(
            "E1",
            text="报告披露存货增速高于收入增速，毛利率下滑。",
            evidence_type="financial",
        )
    ]

    issues = apply_metric_rules(evidence, config, documents=[])

    assert issues
    for issue in issues:
        assert re.fullmatch(r"ISSUE-[A-Za-z0-9][A-Za-z0-9._-]*", issue.issue_id)
        assert issue.status == "open"
