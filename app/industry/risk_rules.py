"""Industry risk rule application (C role)."""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from app.schemas import Claim, Evidence, IndustryConfig, RiskRule


def _stable_claim_id(kind: str, raw_id: str) -> str:
    """Create a legal, readable, collision-resistant Claim ID."""

    readable = re.sub(r"[^A-Za-z0-9]+", "-", raw_id).strip("-").upper() or "ITEM"
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"CL-{kind}-{readable[:32]}-{digest}"


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


def _evidence_mentions_any(item: Evidence, terms: list[str]) -> bool:
    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(term.casefold() in searchable for term in terms)


def _covered_metric_ids(item: Evidence, config: IndustryConfig) -> set[str]:
    """Return metric IDs this Evidence can cover.

    A metric is covered only when the Evidence type is allowed by that
    metric's ``evidence_types`` and at least one keyword appears.
    """

    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return {
        metric.metric_id
        for metric in config.required_metrics
        if item.evidence_type in metric.evidence_types
        and any(keyword.casefold() in searchable for keyword in metric.keywords)
    }


def _risk_claim(
    rule: RiskRule,
    evidence_ids: list[str],
    text: str,
    confidence: float,
    claim_type: Literal["risk", "unresolved"],
) -> Claim:
    return Claim(
        claim_id=_stable_claim_id("RISK", rule.risk_id),
        text=text,
        claim_type=claim_type,
        risk_severity=rule.severity,
        evidence_ids=evidence_ids,
        calculation=None,
        confidence=confidence,
        industry_metric_ids=rule.metric_ids,
        status="review",
    )


def apply_risk_rules(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Apply every configured risk rule and return structured Claims.

    A risk Claim is produced only when:
    - every ``required_evidence_type`` has at least one supporting Evidence;
    - supporting Evidence mentions one of the rule's explicit ``trigger_terms``
      and does not mention any ``exclude_terms``;
    - every ``metric_ids`` entry is covered by Evidence whose type is allowed
      by that metric's ``evidence_types``.

    Otherwise an unresolved Claim keeps the gap visible.
    """

    verified = _scoped_verified_evidence(evidence, config)
    claims: list[Claim] = []

    for rule in config.risk_rules:
        if not rule.required_evidence_types:
            claims.append(
                _risk_claim(
                    rule,
                    [],
                    f"风险规则“{rule.display_name}”没有配置所需证据类型，无法判断。",
                    0.0,
                    "unresolved",
                )
            )
            continue

        required_type_set = {item.casefold() for item in rule.required_evidence_types}
        required_metric_set = set(rule.metric_ids)
        supporting: list[Evidence] = []
        metric_supporting: list[Evidence] = []
        covered_metrics_by_evidence: dict[str, set[str]] = {}

        for item in verified:
            if item.evidence_type.casefold() not in required_type_set:
                continue
            if not _evidence_mentions_any(item, rule.trigger_terms):
                continue
            if _evidence_mentions_any(item, rule.exclude_terms):
                continue
            supporting.append(item)

            covered = _covered_metric_ids(item, config)
            if covered & required_metric_set:
                covered_metrics_by_evidence[item.evidence_id] = covered
                metric_supporting.append(item)

        supporting_by_type: dict[str, list[Evidence]] = {}
        for item in supporting:
            supporting_by_type.setdefault(item.evidence_type.casefold(), []).append(item)

        evidence_ids = list(dict.fromkeys(item.evidence_id for item in supporting))

        missing_types = [
            evidence_type
            for evidence_type in rule.required_evidence_types
            if not supporting_by_type.get(evidence_type.casefold())
        ]
        if missing_types:
            claims.append(
                _risk_claim(
                    rule,
                    evidence_ids,
                    (
                        f"风险规则“{rule.display_name}”仍缺少证据类型："
                        f"{', '.join(missing_types)}。"
                    ),
                    0.0,
                    "unresolved",
                )
            )
            continue

        covered_metric_ids = (
            set().union(*covered_metrics_by_evidence.values())
            if covered_metrics_by_evidence
            else set()
        )
        missing_metrics = [
            metric_id for metric_id in rule.metric_ids if metric_id not in covered_metric_ids
        ]
        if missing_metrics:
            claims.append(
                _risk_claim(
                    rule,
                    evidence_ids,
                    (
                        f"风险规则“{rule.display_name}”仍缺少观察指标证据："
                        f"{', '.join(missing_metrics)}。"
                    ),
                    0.0,
                    "unresolved",
                )
            )
            continue

        exclusion_evidence = [
            item
            for item in verified
            if _evidence_mentions_any(item, rule.exclude_terms)
        ]
        if supporting and exclusion_evidence:
            conflict_evidence_ids = list(
                dict.fromkeys(
                    evidence_ids + [item.evidence_id for item in exclusion_evidence]
                )
            )
            claims.append(
                _risk_claim(
                    rule,
                    conflict_evidence_ids,
                    (
                        f"风险规则“{rule.display_name}”同时存在触发与排除/缓解信号，"
                        f"需人工确认后才能判断风险是否成立。"
                    ),
                    0.0,
                    "unresolved",
                )
            )
            continue

        claims.append(
            _risk_claim(
                rule,
                evidence_ids,
                (
                    f"风险规则“{rule.display_name}”已获得所需证据，"
                    f"需人工确认：{rule.trigger_description}"
                ),
                min(item.confidence for item in metric_supporting),
                "risk",
            )
        )

    return claims
