"""Industry checklist and required-metric coverage checks (C role)."""

from __future__ import annotations

from app.schemas import Evidence, IndustryConfig, SourceDocument, ValidationIssue

#: Evidence types accepted by B's locator and recommended in CONTRACTS.
_ALLOWED_EVIDENCE_TYPES = frozenset(
    {"financial", "operating", "policy", "news", "company_release", "market_data", "other"}
)

#: Map MetricRule.missing_action to ValidationIssue.severity, consistent with A's Critic.
_MISSING_ACTION_SEVERITY = {
    "warn": "warning",
    "review": "error",
    "reject": "critical",
}


def build_industry_checklist(config: IndustryConfig) -> list[str]:
    """Return the metric IDs that must be checked for this industry.

    Only metrics with ``required=True`` are part of the checklist.
    """

    return [metric.metric_id for metric in config.required_metrics if metric.required]


def _evidence_matches_metric(
    item: Evidence,
    config: IndustryConfig,
    metric_id: str,
    keywords: list[str],
) -> bool:
    """Return True when one Evidence item can cover one metric.

    Coverage requires:
    - verified status;
    - explicit industry match (``None`` is unknown, not wildcard);
    - a recognized evidence type;
    - at least one metric keyword present in the fact or quote.
    """

    if item.review_status != "verified":
        return False
    if item.industry_id != config.industry_id:
        return False
    if item.evidence_type not in _ALLOWED_EVIDENCE_TYPES:
        return False

    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(keyword.casefold() in searchable for keyword in keywords)


def _independent_sources(
    evidence_items: list[Evidence],
    documents: list[SourceDocument],
) -> bool:
    """Return True when evidence has at least two independent sources.

    Independence follows CONTRACT-CHANGE-002: at least two different
    publishers and at least two different content hashes. Evidence whose
    document is missing is not counted.
    """

    doc_by_id = {document.doc_id: document for document in documents}
    sources: list[tuple[str, str]] = []
    for item in evidence_items:
        document = doc_by_id.get(item.doc_id)
        if document is None:
            continue
        sources.append((document.publisher, document.content_hash))

    publishers = {publisher for publisher, _ in sources}
    content_hashes = {content_hash for _, content_hash in sources}
    return len(publishers) >= 2 and len(content_hashes) >= 2


def _make_issue(metric, message: str, issue_type: str) -> ValidationIssue:
    return ValidationIssue(
        issue_id=f"ISSUE-C002-{metric.metric_id}",
        check_name="required_metric_coverage",
        severity=_MISSING_ACTION_SEVERITY[metric.missing_action],
        issue_type=issue_type,
        message=message,
        claim_id=None,
        evidence_id=None,
        report_section=None,
        rerun_required=True,
        human_confirmation_required=metric.missing_action in {"review", "reject"},
        status="open",
    )


def check_required_metrics(
    evidence: list[Evidence],
    config: IndustryConfig,
    *,
    documents: list[SourceDocument],
) -> list[ValidationIssue]:
    """Check that every required metric has sufficient verified evidence.

    Missing or insufficiently supported metrics produce ``ValidationIssue``
    objects. Optional metrics are never checked.
    """

    issues: list[ValidationIssue] = []

    for metric in config.required_metrics:
        if not metric.required:
            continue

        matching_evidence = [
            item
            for item in evidence
            if _evidence_matches_metric(
                item,
                config,
                metric_id=metric.metric_id,
                keywords=metric.keywords,
            )
        ]

        if not matching_evidence:
            issues.append(
                _make_issue(
                    metric,
                    (
                        f"E202 module=industry.checklist: required metric "
                        f"{metric.metric_id} ({metric.display_name}) has no "
                        f"verified evidence matching its keywords; "
                        f"missing_action={metric.missing_action}"
                    ),
                    issue_type="missing_metric",
                )
            )
            continue

        if metric.evidence_requirement == "multiple":
            if not _independent_sources(matching_evidence, documents):
                issues.append(
                    _make_issue(
                        metric,
                        (
                            f"E202 module=industry.checklist: required metric "
                            f"{metric.metric_id} ({metric.display_name}) requires "
                            f"at least two independent sources (different publisher "
                            f"and different content_hash); missing_action={metric.missing_action}"
                        ),
                        issue_type="insufficient_evidence",
                    )
                )

    return issues
