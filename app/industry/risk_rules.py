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


def _risk_trigger_terms(rule: RiskRule, config: IndustryConfig) -> list[str]:
    """Return explicit content terms that can support one risk rule."""

    text = f"{rule.risk_id} {rule.display_name} {rule.trigger_description}".casefold()
    terms = [rule.display_name, rule.trigger_description]
    for metric in config.required_metrics:
        if metric.metric_id.casefold() in text or metric.display_name.casefold() in text:
            terms.extend(metric.keywords)
    return [term.casefold() for term in terms if term]


def _evidence_mentions(item: Evidence, terms: list[str]) -> bool:
    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(term in searchable for term in terms)


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

    A risk Claim is only produced when each required evidence type has at
    least one verified, industry-scoped Evidence that also mentions the rule's
    trigger content. Otherwise an unresolved Claim keeps the gap visible.
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

        supporting_by_type = {
            evidence_type: [
                item
                for item in verified
                if item.evidence_type.casefold() == evidence_type.casefold()
            ]
            for evidence_type in rule.required_evidence_types
        }
        supporting = [
            item for items in supporting_by_type.values() for item in items
        ]
        evidence_ids = list(dict.fromkeys(item.evidence_id for item in supporting))

        missing_types = [
            evidence_type
            for evidence_type in rule.required_evidence_types
            if not supporting_by_type[evidence_type]
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

        trigger_terms = _risk_trigger_terms(rule, config)
        relevant_by_type = {
            evidence_type: [
                item for item in items if _evidence_mentions(item, trigger_terms)
            ]
            for evidence_type, items in supporting_by_type.items()
        }
        unrelated_types = [
            evidence_type
            for evidence_type, items in relevant_by_type.items()
            if not items
        ]
        if unrelated_types:
            claims.append(
                _risk_claim(
                    rule,
                    evidence_ids,
                    (
                        f"风险规则“{rule.display_name}”的证据类型未分别支持触发条件："
                        f"{', '.join(unrelated_types)}。"
                    ),
                    0.0,
                    "unresolved",
                )
            )
            continue

        relevant = [
            item for items in relevant_by_type.values() for item in items
        ]
        claims.append(
            _risk_claim(
                rule,
                list(dict.fromkeys(item.evidence_id for item in relevant)),
                (
                    f"风险规则“{rule.display_name}”已获得所需证据，"
                    f"需人工确认：{rule.trigger_description}"
                ),
                min(item.confidence for item in relevant),
                "risk",
            )
        )

    return claims
