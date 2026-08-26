"""Evidence-bound fundamental analysis node."""

from __future__ import annotations

from app.schemas import Claim, Evidence, IndustryConfig, MetricRule, SourceDocument

from ._helpers import scoped_verified_evidence, stable_claim_id


def _matches_metric(item: Evidence, metric: MetricRule) -> bool:
    if item.evidence_type not in metric.evidence_types:
        return False
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


def _has_independent_sources(
    matches: list[Evidence],
    documents: list[SourceDocument] | None,
) -> bool:
    """Require distinct publishers and distinct content hashes for independence."""

    if documents is None:
        return False
    doc_by_id = {document.doc_id: document for document in documents}
    matched_documents = [
        doc_by_id[item.doc_id]
        for item in matches
        if item.doc_id in doc_by_id
    ]
    publishers = {document.publisher.strip().casefold() for document in matched_documents}
    content_hashes = {document.content_hash for document in matched_documents}
    return len(publishers) >= 2 and len(content_hashes) >= 2


def analyze_fundamentals(
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument] | None = None,
) -> list[Claim]:
    """Create direct fact Claims for evidence-backed industry metrics.

    ``multiple`` metrics require SourceDocument metadata and pass only when at
    least two distinct publishers and two distinct content hashes support the
    metric. Different ``doc_id`` values alone are insufficient.
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

        if metric.evidence_requirement == "multiple" and not _has_independent_sources(
            matches, documents
        ):
            claims.append(
                _unresolved_claim(
                    metric,
                    evidence_ids,
                    f"{metric.display_name}要求至少两个独立发布主体和不同内容哈希的来源。",
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
