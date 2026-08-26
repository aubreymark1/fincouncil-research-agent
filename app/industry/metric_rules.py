"""Industry metric-level rules (C role, C-004).

These rules inspect the same Evidence pool as the checklist and risk rules
but surface metric-level gaps and inconsistencies as ``ValidationIssue``
objects. They never rewrite or create ``Claim`` text: they only flag items
that need human confirmation or additional evidence.

Contract alignment:
- Only verified Evidence scoped to ``config.industry_id`` is inspected.
- Metric coverage follows ``MetricRule.evidence_types`` and keywords from the
  loaded ``IndustryConfig`` so the rules stay in sync with the YAML configs.
- Every issue carries a stable ``ISSUE-C004-*`` id and a contract error code
  (E202 family for metric-level gaps) in the message text.
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable

from app.schemas import Evidence, IndustryConfig, SourceDocument, ValidationIssue

# Error code shared with the checklist for metric-level gaps.
_ERROR_CODE = "E202"

# --------------------------------------------------------------------------
# Shared helpers (kept local to avoid coupling to private names in sibling
# modules; same conventions as checklist.py / risk_rules.py).
# --------------------------------------------------------------------------


def _scoped_verified_evidence(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Evidence]:
    """Keep only verified evidence explicitly scoped to the target industry."""

    return [
        item
        for item in evidence
        if item.review_status == "verified" and item.industry_id == config.industry_id
    ]


def _metric_by_id(config: IndustryConfig) -> dict[str, object]:
    return {metric.metric_id: metric for metric in config.required_metrics}


def _normalised_keywords(metric: object) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for keyword in getattr(metric, "keywords", []):
        normalised = keyword.strip().casefold()
        if normalised and normalised not in seen:
            seen.add(normalised)
            result.append(normalised)
    return result


def _searchable(item: Evidence) -> str:
    return f"{item.fact_text}\n{item.quote}".casefold()


def _mentions_any(item: Evidence, terms: list[str]) -> bool:
    searchable = _searchable(item)
    return any(term.casefold() in searchable for term in terms)


def _pool_mentions_any(items: list[Evidence], terms: list[str]) -> bool:
    return any(_mentions_any(item, terms) for item in items)


def _evidence_covers_metric(
    item: Evidence,
    metric: object,
) -> bool:
    """Return True when one Evidence item covers a metric.

    Coverage requires the Evidence type to be allowed by the metric's
    ``evidence_types`` and at least one metric keyword to appear.
    """

    if item.evidence_type not in getattr(metric, "evidence_types", []):
        return False
    searchable = _searchable(item)
    return any(keyword in searchable for keyword in _normalised_keywords(metric))


def _evidence_for_metric(
    evidence: list[Evidence],
    config: IndustryConfig,
    metric_id: str,
) -> list[Evidence]:
    metric = _metric_by_id(config).get(metric_id)
    if metric is None:
        return []
    return [item for item in evidence if _evidence_covers_metric(item, metric)]


def _make_issue(
    rule_id: str,
    issue_type: str,
    message: str,
    *,
    severity: str = "warning",
    evidence_id: str | None = None,
) -> ValidationIssue:
    """Build a deterministic, schema-valid ValidationIssue for one rule."""

    readable = re.sub(r"[^A-Za-z0-9]+", "-", rule_id).strip("-").upper() or "RULE"
    digest = hashlib.sha256(rule_id.encode("utf-8")).hexdigest()[:10].upper()
    return ValidationIssue(
        issue_id=f"ISSUE-C004-{readable}-{digest}",
        check_name="metric_rule_check",
        severity=severity,  # type: ignore[arg-type]
        issue_type=issue_type,
        message=message,
        claim_id=None,
        evidence_id=evidence_id,
        report_section=None,
        rerun_required=True,
        human_confirmation_required=True,
        status="open",
    )


# --------------------------------------------------------------------------
# Rule vocabularies. These are rule-specific (not metric keywords) and
# intentionally narrow to avoid false positives.
# --------------------------------------------------------------------------

# Food beverage: inventory growth must be compared against revenue growth.
_FOOD_INVENTORY_GROWTH_TERMS = [
    "存货增速高于收入增速",
    "存货增速明显高于收入增速",
    "存货增速快于收入",
    "存货增长快于收入",
    "存货增速超过收入增速",
]
_FOOD_INVENTORY_TERMS = ["存货增速", "存货增长", "存货余额增长", "存货上升"]

# Food beverage: gross margin change must state a comparison period.
_FOOD_MARGIN_CHANGE_TERMS = [
    "毛利率下滑",
    "毛利率下降",
    "毛利率降低",
    "毛利率上升",
    "毛利率提高",
    "毛利率恶化",
    "毛利率变化",
    "毛利率降低",
]
_PERIOD_TERMS = [
    "同比",
    "环比",
    "较上年",
    "较上期",
    "较去年同期",
    "上年同期",
    "上期",
    "去年同期",
]

# Food beverage: volume and price must not substitute for each other.
_FOOD_VOLUME_TERMS = ["销量", "销售量", "出货量"]
_FOOD_PRICE_TERMS = ["价格", "单价", "吨价", "出厂价"]
_FOOD_SUBSTITUTION_TERMS = [
    "换算",
    "推算",
    "折算",
    "相当于",
    "约等于",
    "推算出",
    "折合",
]

# Food beverage: management plans must not be written as completed facts.
_FOOD_PLAN_TERMS = [
    "计划",
    "拟",
    "预计",
    "目标",
    "规划",
    "力争",
    "拟于",
    "将要",
    "将",
]
_FOOD_COMPLETION_TERMS = [
    "已完成",
    "已实现",
    "已经达到",
    "已经完成",
    "已达成",
]

# Banking: NPL, watch-class loans and provision coverage joint check.
_BANK_NPL_CHANGE_TERMS = [
    "不良率上升",
    "不良率下降",
    "不良率恶化",
    "不良贷款率上升",
    "不良贷款率下降",
    "不良贷款率恶化",
]
_BANK_WATCH_TERMS = ["关注类贷款", "关注类"]

# Banking: NIM change must state a period.
# Direction terms are intentionally bare: the NIM rule first filters Evidence
# through the ``net_interest_margin`` metric (config keywords + evidence_types),
# so any NIM synonym declared in ``configs/banking.yaml`` (净息差 / 净利息收益率
# / 息差) is automatically reused. This avoids drift between the rule and YAML.
_BANK_NIM_DIRECTION_TERMS = [
    "下降",
    "上升",
    "下滑",
    "变化",
    "收窄",
    "扩大",
    "降低",
    "提高",
    "恶化",
    "改善",
]

# Banking: capital adequacy ratio must preserve original caliber.
_BANK_CAPITAL_TERMS = ["资本充足率", "核心一级资本充足率", "一级资本充足率"]
_BANK_CAPITAL_CHANGE_TERMS = [
    "资本充足率下降",
    "资本充足率上升",
    "资本充足率下滑",
    "资本充足率低于",
    "资本充足率高于",
    "资本充足率压力",
]
_BANK_CALIBER_TERMS = [
    "口径",
    "核心一级",
    "一级资本",
    "风险加权资产",
    "重述",
    "新口径",
    "原口径",
]

# Banking: real-estate industry news cannot be directly mapped to a target bank.
_BANK_REAL_ESTATE_TERMS = [
    "房地产贷款",
    "房地产风险",
    "开发贷",
    "按揭贷款",
]
_BANK_NEWS_TYPES = {"news", "policy"}


# --------------------------------------------------------------------------
# Food beverage rules.
# --------------------------------------------------------------------------


def _food_inventory_growth_vs_revenue(
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument],  # noqa: ARG003 - reserved for parity
) -> ValidationIssue | None:
    """Flag inventory-growth evidence that lacks a revenue-growth comparison.

    Two distinct signals:
    - Explicit "inventory grew faster than revenue" phrasing -> ask a human to
      confirm the comparison period and absolute figures.
    - Inventory growth mentioned but no ``revenue_growth`` metric evidence -> the
      comparison cannot be made at all.
    """

    if _pool_mentions_any(evidence, _FOOD_INVENTORY_GROWTH_TERMS):
        return _make_issue(
            "inventory_growth_vs_revenue",
            "inventory_growth_over_revenue",
            (
                f"{_ERROR_CODE} module=industry.metric_rules: evidence states inventory "
                "growth exceeds revenue growth; confirm the comparison period and "
                "absolute figures against source documents."
            ),
        )
    if _pool_mentions_any(evidence, _FOOD_INVENTORY_TERMS):
        revenue_evidence = _evidence_for_metric(evidence, config, "revenue_growth")
        if not revenue_evidence:
            return _make_issue(
                "inventory_growth_vs_revenue",
                "inventory_growth_without_revenue",
                (
                    f"{_ERROR_CODE} module=industry.metric_rules: inventory growth "
                    "is mentioned, but no revenue_growth evidence is available "
                    "to confirm the comparison."
                ),
            )
    return None


def _food_gross_margin_period(
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag gross-margin change evidence that does not state a period."""

    margin_evidence = _evidence_for_metric(evidence, config, "gross_margin")
    flagged: list[Evidence] = []
    for item in margin_evidence:
        if _mentions_any(item, _FOOD_MARGIN_CHANGE_TERMS) and not _mentions_any(
            item, _PERIOD_TERMS
        ):
            flagged.append(item)
    if not flagged:
        return None
    return _make_issue(
        "gross_margin_missing_period",
        "gross_margin_missing_period",
        (
            f"{_ERROR_CODE} module=industry.metric_rules: gross-margin change "
            "evidence does not state a comparison period (同比/环比/较上年); "
            "require explicit period before use in claims."
        ),
        evidence_id=flagged[0].evidence_id,
    )


def _food_volume_price_substitution(
    evidence: list[Evidence],
    config: IndustryConfig,  # noqa: ARG003
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag evidence that substitutes price for volume (or vice versa)."""

    for item in evidence:
        if (
            _mentions_any(item, _FOOD_VOLUME_TERMS)
            and _mentions_any(item, _FOOD_PRICE_TERMS)
            and _mentions_any(item, _FOOD_SUBSTITUTION_TERMS)
        ):
            return _make_issue(
                "volume_price_substitution",
                "volume_price_substitution",
                (
                    f"{_ERROR_CODE} module=industry.metric_rules: evidence mixes "
                    "volume and price with a substitution phrase "
                    "(换算/推算/折算/相当于); volume and price must be backed by "
                    "separate evidence."
                ),
                evidence_id=item.evidence_id,
            )
    return None


def _food_management_plan_as_fact(
    evidence: list[Evidence],
    config: IndustryConfig,  # noqa: ARG003
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag evidence that states a management plan as a completed fact."""

    for item in evidence:
        if _mentions_any(item, _FOOD_PLAN_TERMS) and _mentions_any(
            item, _FOOD_COMPLETION_TERMS
        ):
            return _make_issue(
                "management_plan_as_fact",
                "management_plan_as_fact",
                (
                    f"{_ERROR_CODE} module=industry.metric_rules: evidence combines "
                    "a management plan term with a completion assertion; management "
                    "plans cannot be reported as completed facts."
                ),
                severity="error",
                evidence_id=item.evidence_id,
            )
    return None


# --------------------------------------------------------------------------
# Banking rules.
# --------------------------------------------------------------------------


def _bank_npl_provision_joint(
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag NPL change evidence lacking provision-coverage / watch-class context.

    Provision-coverage context must come from Evidence that satisfies the
    ``provision_coverage`` metric (its ``evidence_types`` filter, financial in
    the banking config) and mentions the metric's keywords. A news-only mention
    of 拨备 does not satisfy the joint check. 关注类贷款 has no dedicated
    metric, so it is still matched at the pool level.
    """

    npl_evidence = _evidence_for_metric(evidence, config, "non_performing_loan_ratio")
    if not npl_evidence:
        return None
    npl_change_items = [
        item for item in npl_evidence if _mentions_any(item, _BANK_NPL_CHANGE_TERMS)
    ]
    if not npl_change_items:
        return None
    provision_evidence = _evidence_for_metric(evidence, config, "provision_coverage")
    has_provision = bool(provision_evidence)
    has_watch = _pool_mentions_any(evidence, _BANK_WATCH_TERMS)
    missing: list[str] = []
    if not has_provision:
        missing.append("拨备覆盖率")
    if not has_watch:
        missing.append("关注类贷款")
    if not missing:
        return None
    return _make_issue(
        "npl_provision_joint_check",
        "npl_provision_joint_incomplete",
        (
            f"{_ERROR_CODE} module=industry.metric_rules: NPL change evidence "
            f"requires joint check with {', '.join(missing)}; current evidence "
            "pool does not provide them with the required evidence_types."
        ),
        evidence_id=npl_change_items[0].evidence_id,
    )


def _bank_nim_period(
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag NIM change evidence that does not state a period.

    A change is detected when an Evidence item covers the
    ``net_interest_margin`` metric (config keywords + evidence_types) and
    mentions a direction term. NIM synonyms come from the loaded config, so
    the rule stays in sync with ``configs/banking.yaml`` automatically.
    """

    nim_evidence = _evidence_for_metric(evidence, config, "net_interest_margin")
    flagged: list[Evidence] = []
    for item in nim_evidence:
        if _mentions_any(item, _BANK_NIM_DIRECTION_TERMS) and not _mentions_any(
            item, _PERIOD_TERMS
        ):
            flagged.append(item)
    if not flagged:
        return None
    return _make_issue(
        "nim_missing_period",
        "nim_missing_period",
        (
            f"{_ERROR_CODE} module=industry.metric_rules: NIM change evidence "
            "does not state a comparison period (同比/环比/较上年); require "
            "explicit period before use in claims."
        ),
        evidence_id=flagged[0].evidence_id,
    )


def _bank_capital_adequacy_caliber(
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag capital-adequacy change evidence that does not preserve caliber."""

    capital_evidence = _evidence_for_metric(evidence, config, "capital_adequacy")
    flagged: list[Evidence] = []
    for item in capital_evidence:
        if _mentions_any(item, _BANK_CAPITAL_TERMS) and _mentions_any(
            item, _BANK_CAPITAL_CHANGE_TERMS
        ) and not _mentions_any(item, _BANK_CALIBER_TERMS):
            flagged.append(item)
    if not flagged:
        return None
    return _make_issue(
        "capital_adequacy_caliber",
        "capital_adequacy_caliber_unverified",
        (
            f"{_ERROR_CODE} module=industry.metric_rules: capital-adequacy change "
            "evidence does not state the regulatory caliber "
            "(口径/核心一级/一级资本/风险加权资产); original caliber must be preserved."
        ),
        evidence_id=flagged[0].evidence_id,
    )


def _bank_real_estate_news_not_specific(
    evidence: list[Evidence],
    config: IndustryConfig,
    documents: list[SourceDocument],  # noqa: ARG003
) -> ValidationIssue | None:
    """Flag real-estate industry news not backed by target-bank exposure evidence."""

    news_real_estate = [
        item
        for item in evidence
        if item.evidence_type in _BANK_NEWS_TYPES
        and _mentions_any(item, _BANK_REAL_ESTATE_TERMS)
    ]
    if not news_real_estate:
        return None
    financial_exposure = [
        item
        for item in _evidence_for_metric(evidence, config, "real_estate_exposure")
        if item.evidence_type == "financial"
    ]
    if financial_exposure:
        return None
    return _make_issue(
        "real_estate_news_not_bank_specific",
        "real_estate_news_not_bank_specific",
        (
            f"{_ERROR_CODE} module=industry.metric_rules: real-estate industry news "
            "cannot be directly mapped to the target bank; require target-bank "
            "financial exposure evidence (real_estate_exposure metric)."
        ),
        severity="error",
        evidence_id=news_real_estate[0].evidence_id,
    )


# --------------------------------------------------------------------------
# Dispatch table.
# --------------------------------------------------------------------------

_RuleFn = Callable[[list[Evidence], IndustryConfig, list[SourceDocument]], ValidationIssue | None]

_FOOD_RULES: list[_RuleFn] = [
    _food_inventory_growth_vs_revenue,
    _food_gross_margin_period,
    _food_volume_price_substitution,
    _food_management_plan_as_fact,
]

_BANK_RULES: list[_RuleFn] = [
    _bank_npl_provision_joint,
    _bank_nim_period,
    _bank_capital_adequacy_caliber,
    _bank_real_estate_news_not_specific,
]

_RULES_BY_INDUSTRY: dict[str, list[_RuleFn]] = {
    "food_beverage": _FOOD_RULES,
    "banking": _BANK_RULES,
}


def apply_metric_rules(
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument],
) -> list[ValidationIssue]:
    """Apply industry-specific metric rules and return ``ValidationIssue`` items.

    Rules never rewrite or create ``Claim`` text. They only surface metric-level
    gaps that need human confirmation or additional evidence, complementing
    the checklist (required-metric coverage) and the risk rules (risk Claims).

    Only verified Evidence scoped to ``config.industry_id`` is inspected.
    Industries without registered rules return an empty list rather than
    failing, so the module stays usable for future industries without changes.
    """

    scoped = _scoped_verified_evidence(evidence, config)
    rules = _RULES_BY_INDUSTRY.get(config.industry_id, [])
    issues: list[ValidationIssue] = []
    for rule in rules:
        issue = rule(scoped, config, documents)
        if issue is not None:
            issues.append(issue)
    return issues
