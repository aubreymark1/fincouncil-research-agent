"""Evidence-bound industry risk analysis node."""

from __future__ import annotations

from typing import Literal

from app.schemas import Claim, Evidence, IndustryConfig, RiskRule


def _risk_claim(
    rule: RiskRule,
    evidence_ids: list[str],
    text: str,
    confidence: float,
    claim_type: Literal["risk", "unresolved"],
) -> Claim:
    return Claim(
        claim_id=f"CL-RISK-{rule.risk_id}",
        text=text,
        claim_type=claim_type,
        evidence_ids=evidence_ids,
        calculation=None,
        confidence=confidence,
        industry_metric_ids=[],
        status="review",
    )


def analyze_risks(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Create reviewable risk Claims only when configured evidence types exist."""

    verified = [item for item in evidence if item.review_status == "verified"]
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

        supporting = [
            item
            for evidence_type in rule.required_evidence_types
            for item in verified
            if item.evidence_type.casefold() == evidence_type.casefold()
        ]
        evidence_ids = list(dict.fromkeys(item.evidence_id for item in supporting))
        missing_types = [
            evidence_type
            for evidence_type in rule.required_evidence_types
            if not any(item.evidence_type.casefold() == evidence_type.casefold() for item in verified)
        ]
        if missing_types:
            claims.append(
                _risk_claim(
                    rule,
                    evidence_ids,
                    f"风险规则“{rule.display_name}”仍缺少证据类型：{', '.join(missing_types)}。",
                    0.0,
                    "unresolved",
                )
            )
            continue

        claims.append(
            _risk_claim(
                rule,
                evidence_ids,
                f"风险规则“{rule.display_name}”已获得所需证据，需人工确认：{rule.trigger_description}",
                min(item.confidence for item in supporting),
                "risk",
            )
        )
    return claims
