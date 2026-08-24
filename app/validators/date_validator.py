"""Cutoff-date filtering for source documents."""

from __future__ import annotations

from datetime import date

from app.schemas import SourceDocument, ValidationIssue


def _issue(
    *,
    document: SourceDocument,
    issue_suffix: str,
    severity: str,
    issue_type: str,
    message: str,
    human_confirmation_required: bool,
    status: str,
) -> ValidationIssue:
    """Build a stable, source-specific time-lock issue."""

    return ValidationIssue(
        issue_id=f"ISSUE-TIME-{document.doc_id.removeprefix('DOC-')}-{issue_suffix}",
        check_name="time_lock",
        severity=severity,
        issue_type=issue_type,
        message=message,
        claim_id=None,
        evidence_id=None,
        report_section="source_filter",
        rerun_required=False,
        human_confirmation_required=human_confirmation_required,
        status=status,
    )


def apply_time_lock(
    documents: list[SourceDocument],
    cutoff_date: date,
) -> tuple[list[SourceDocument], list[ValidationIssue]]:
    """Return documents published no later than ``cutoff_date``.

    Documents without a publication date are withheld for manual verification.
    A document published by the cutoff remains eligible even when its event date
    is later; the distinction is preserved as an informational issue so later
    reporting can make that temporal boundary visible.
    """

    allowed_documents: list[SourceDocument] = []
    issues: list[ValidationIssue] = []

    for document in documents:
        if document.published_at is None:
            issues.append(
                _issue(
                    document=document,
                    issue_suffix="MISSING-PUBLISHED-AT",
                    severity="warning",
                    issue_type="missing_published_at",
                    message=(
                        f"E102 {document.doc_id} lacks published_at and is held for manual verification."
                    ),
                    human_confirmation_required=True,
                    status="open",
                )
            )
            continue

        if document.published_at > cutoff_date:
            issues.append(
                _issue(
                    document=document,
                    issue_suffix="PUBLISHED-AFTER-CUTOFF",
                    severity="critical",
                    issue_type="published_after_cutoff",
                    message=(
                        f"E103 {document.doc_id} was published on {document.published_at.isoformat()}, "
                        f"after cutoff {cutoff_date.isoformat()}, and was rejected by the time lock."
                    ),
                    human_confirmation_required=False,
                    status="open",
                )
            )
            continue

        allowed_documents.append(document)

        if document.event_date is not None and document.event_date > cutoff_date:
            issues.append(
                _issue(
                    document=document,
                    issue_suffix="EVENT-AFTER-CUTOFF",
                    severity="info",
                    issue_type="event_after_cutoff",
                    message=(
                        f"{document.doc_id} was published by the cutoff, but its event_date "
                        f"({document.event_date.isoformat()}) is later than cutoff "
                        f"({cutoff_date.isoformat()}); the document remains allowed with this note."
                    ),
                    human_confirmation_required=False,
                    status="accepted_risk",
                )
            )

    return allowed_documents, issues
