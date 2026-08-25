"""Evidence-bound news and policy analysis node."""

from __future__ import annotations

from app.schemas import Claim, Evidence, IndustryConfig

from ._helpers import scoped_verified_evidence, stable_claim_id


_NEWS_POLICY_TYPES = {"news", "policy", "company_release"}


def analyze_news_policy(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Create reviewable change Claims from verified news or policy evidence."""

    relevant = [
        item
        for item in scoped_verified_evidence(evidence, config)
        if item.evidence_type.casefold() in _NEWS_POLICY_TYPES
    ]
    if not relevant:
        return [
            Claim(
                claim_id="CL-NEWS-POLICY-UNRESOLVED",
                text="未找到可核验的新闻或政策证据。",
                claim_type="unresolved",
                evidence_ids=[],
                calculation=None,
                confidence=0.0,
                industry_metric_ids=[],
                status="review",
            )
        ]

    return [
        Claim(
            claim_id=stable_claim_id("NEWS-POLICY", item.evidence_id),
            text=item.fact_text,
            claim_type="change",
            evidence_ids=[item.evidence_id],
            calculation=None,
            confidence=item.confidence,
            industry_metric_ids=[],
            status="review",
        )
        for item in relevant
    ]
