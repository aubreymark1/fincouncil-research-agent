"""Industry checklist and required-metric coverage checks (C role)."""

from __future__ import annotations

import hashlib
import re

from app.schemas import (
    ALLOWED_EVIDENCE_TYPES,
    Evidence,
    IndustryConfig,
    SourceDocument,
    ValidationIssue,
)

#: Map MetricRule.missing_action to ValidationIssue.severity, consistent with A's Critic.
_MISSING_ACTION_SEVERITY = {
    "warn": "warning",
    "review": "error",
    "reject": "critical",
}


def _normalise_keywords(keywords: list[str]) -> list[str]:
    """Strip, casefold, de-duplicate, and drop blank metric keywords."""

    seen: set[str] = set()
    result: list[str] = []
    for keyword in keywords:
        normalized = keyword.strip().casefold()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def build_industry_checklist(config: IndustryConfig) -> list[str]:
    """Return the metric IDs that must be checked for this industry.

    Only metrics with ``required=True`` are part of the checklist.
    """

    return [metric.metric_id for metric in config.required_metrics if metric.required]


def _evidence_matches_source_document(
    item: Evidence,
    document: SourceDocument,
) -> bool:
    """Return True when Evidence metadata is consistent with its SourceDocument.

    CONTRACT-CHANGE-002 requires Evidence to copy ``published_at``,
    ``company_name`` and ``industry_id`` from its SourceDocument, so any
    inconsistency means the evidence cannot be trusted for coverage.
    """

    if item.doc_id != document.doc_id:
        return False
    if item.published_at != document.published_at:
        return False
    if item.industry_id != document.industry_id:
        return False
    if item.company_name != document.company_name:
        return False
    return True


def _evidence_matches_metric(
    item: Evidence,
    config: IndustryConfig,
    metric,
) -> bool:
    """Return True when one Evidence item can cover one metric.

    Coverage requires:
    - verified status;
    - explicit industry match (``None`` is unknown, not wildcard);
    - a recognized evidence type allowed by ``metric.evidence_types``;
    - at least one non-empty metric keyword present in the fact or quote.
    """

    if item.review_status != "verified":
        return False
    if item.industry_id != config.industry_id:
        return False
    if item.evidence_type not in ALLOWED_EVIDENCE_TYPES:
        return False
    if item.evidence_type not in metric.evidence_types:
        return False

    searchable = f"{item.fact_text}\n{item.quote}".casefold()
    return any(keyword in searchable for keyword in _normalise_keywords(metric.keywords))


def _independent_sources(
    evidence_items: list[Evidence],
    documents: list[SourceDocument],
) -> bool:
    """Return True when evidence has at least two independent sources.

    Independence follows CONTRACT-CHANGE-002: at least two different
    publishers and at least two different content hashes. Publisher names are
    normalized (strip + casefold) so cosmetic differences do not create false
    independence. Evidence whose document is missing is not counted.
    """

    doc_by_id = {document.doc_id: document for document in documents}
    sources: list[tuple[str, str]] = []
    for item in evidence_items:
        document = doc_by_id.get(item.doc_id)
        if document is None:
            continue
        publisher = document.publisher.strip().casefold()
        sources.append((publisher, document.content_hash))

    publishers = {publisher for publisher, _ in sources}
    content_hashes = {content_hash for _, content_hash in sources}
    return len(publishers) >= 2 and len(content_hashes) >= 2


def _make_issue(metric, message: str, issue_type: str) -> ValidationIssue:
    """Build a deterministic, schema-valid issue for one metric."""

    digest = hashlib.sha256(metric.metric_id.encode("utf-8")).hexdigest()[:10].upper()
    safe_metric = re.sub(r"[^A-Za-z0-9]+", "-", metric.metric_id).strip("-").upper() or "METRIC"
    return ValidationIssue(
        issue_id=f"ISSUE-C002-{safe_metric}-{digest}",
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

    Only Evidence that can be traced to a matching SourceDocument is counted.
    Missing or insufficiently supported metrics produce ``ValidationIssue``
    objects. Optional metrics are never checked.
    """

    doc_by_id = {document.doc_id: document for document in documents}
    issues: list[ValidationIssue] = []

    for metric in config.required_metrics:
        if not metric.required:
            continue

        matching_evidence = [
            item
            for item in evidence
            if item.doc_id in doc_by_id
            and _evidence_matches_source_document(item, doc_by_id[item.doc_id])
            and _evidence_matches_metric(item, config, metric)
        ]

        if not matching_evidence:
            issues.append(
                _make_issue(
                    metric,
                    (
                        f"E202 module=industry.checklist: required metric "
                        f"{metric.metric_id} ({metric.display_name}) has no "
                        f"verified, source-traced evidence matching its keywords "
                        f"and evidence_types; missing_action={metric.missing_action}"
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
