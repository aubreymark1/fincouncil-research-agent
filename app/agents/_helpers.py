"""Shared safety helpers for evidence-bound analysis nodes."""

from __future__ import annotations

import hashlib
import re

from app.schemas import Evidence, IndustryConfig, RiskRule


def scoped_verified_evidence(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Evidence]:
    """Keep only verified evidence explicitly scoped to the target industry.

    ``industry_id=None`` is treated as unknown, not as a wildcard. Company
    matching remains an upstream responsibility because these A-005 node
    signatures intentionally receive no target company name.
    """

    return [
        item
        for item in evidence
        if item.review_status == "verified" and item.industry_id == config.industry_id
    ]


def stable_claim_id(kind: str, raw_id: str) -> str:
    """Create a legal, readable, collision-resistant Claim ID."""

    readable = re.sub(r"[^A-Za-z0-9]+", "-", raw_id).strip("-").upper() or "ITEM"
    digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"CL-{kind}-{readable[:32]}-{digest}"


def risk_trigger_terms(rule: RiskRule, config: IndustryConfig) -> list[str]:
    """Return explicit content terms that can support one risk rule."""

    text = f"{rule.risk_id} {rule.display_name} {rule.trigger_description}".casefold()
    terms = [rule.display_name, rule.trigger_description]
    for metric in config.required_metrics:
        if metric.metric_id.casefold() in text or metric.display_name.casefold() in text:
            terms.extend(metric.keywords)
    return [term.casefold() for term in terms if term]


def evidence_mentions(item: Evidence, terms: list[str]) -> bool:
    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(term in searchable for term in terms)
