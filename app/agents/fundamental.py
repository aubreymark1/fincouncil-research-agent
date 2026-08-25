"""Evidence-bound fundamental analysis node."""

from __future__ import annotations

from app.schemas import Claim, Evidence, IndustryConfig, MetricRule


def _verified(evidence: list[Evidence]) -> list[Evidence]:
    return [item for item in evidence if item.review_status == "verified"]


def _matches_metric(item: Evidence, metric: MetricRule) -> bool:
    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(keyword.casefold() in searchable for keyword in metric.keywords)


def _unresolved_claim(metric: MetricRule, evidence_ids: list[str], reason: str) -> Claim:
    return Claim(
        claim_id=f"CL-FUND-{metric.metric_id}",
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

    ``multiple`` metrics require evidence from at least two distinct documents.
    Pending and rejected evidence is intentionally excluded; cutoff filtering
    remains the caller's responsibility because this node has no cutoff input.
    """

    verified = _verified(evidence)
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

        distinct_documents = {item.doc_id for item in matches}
        if metric.evidence_requirement == "multiple" and len(distinct_documents) < 2:
            claims.append(
                _unresolved_claim(
                    metric,
                    evidence_ids,
                    f"{metric.display_name}要求至少两个独立来源，当前仅找到一个来源。",
                )
            )
            continue

        primary = matches[0]
        claims.append(
            Claim(
                claim_id=f"CL-FUND-{metric.metric_id}",
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
