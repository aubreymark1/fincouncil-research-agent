"""Evidence-bound fundamental analysis node."""

from __future__ import annotations

from app.schemas import Claim, Evidence, IndustryConfig, MetricRule

from ._helpers import scoped_verified_evidence, stable_claim_id


def _matches_metric(item: Evidence, metric: MetricRule) -> bool:
    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(keyword.casefold() in searchable for keyword in metric.keywords)


def _unresolved_claim(metric: MetricRule, evidence_ids: list[str], reason: str) -> Claim:
    return Claim(
        claim_id=stable_claim_id("FUND", metric.metric_id),
        text=reason,
        claim_type="unresolved",
        evidence_ids=evidence_ids,
        calculation=None,
        confidence=0.0,
        industry_metric_ids=[metric.metric_id],
        status="review",
    )


def analyze_fundamentals(
    evidence: list[Evidence],
    config: IndustryConfig,
) -> list[Claim]:
    """Create direct fact Claims for evidence-backed industry metrics.

    ``multiple`` metrics remain unresolved unless an upstream component has
    confirmed source independence. Evidence currently has no publisher or
    independence field, so different ``doc_id`` values alone are insufficient.
    Pending, rejected, cross-industry, and industry-unknown evidence is
    excluded; cutoff filtering remains the caller's responsibility because this
    node has no cutoff input.
    """

    verified = scoped_verified_evidence(evidence, config)
    claims: list[Claim] = []
    for metric in config.required_metrics:
        matches = [item for item in verified if _matches_metric(item, metric)]
        evidence_ids = [item.evidence_id for item in matches]
        if not matches:
            claims.append(
                _unresolved_claim(
                    metric,
                    [],
                    f"未找到可核验的{metric.display_name}证据。",
                )
            )
            continue

        if metric.evidence_requirement == "multiple":
            claims.append(
                _unresolved_claim(
                    metric,
                    evidence_ids,
                    f"{metric.display_name}要求上游确认独立来源；当前 Evidence 缺少 publisher 或独立性标记。",
                )
            )
            continue

        primary = matches[0]
        claims.append(
            Claim(
                claim_id=stable_claim_id("FUND", metric.metric_id),
                text=primary.fact_text,
                claim_type="fact",
                evidence_ids=evidence_ids,
                calculation=None,
                confidence=min(item.confidence for item in matches),
                industry_metric_ids=[metric.metric_id],
                status="pass",
            )
        )
    return claims
