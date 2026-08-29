"""Deterministic ``pending`` -> ``verified`` policy for located evidence.

docs/CONTRACTS.md Section 五 states that keyword-located evidence stays
``pending`` until confirmed by a human or by an explicit rule. This module
implements that explicit rule for the orchestrator.
"""

from __future__ import annotations

from app.schemas import (
    Evidence,
    ResearchRequest,
    SourceDocument,
    ValidationIssue,
)

AUDIT_ISSUE_ID = "ISSUE-POLICY-EVIDENCE-VERIFICATION"


def _is_verifiable_source(
    document: SourceDocument | None,
    request: ResearchRequest,
    *,
    enforce_cutoff: bool = True,
) -> bool:
    """Check the three upgrade conditions of the explicit verification rule."""

    if document is None or document.review_status != "formal":
        return False
    if document.industry_id != request.industry_id:
        return False
    if document.published_at is None:
        return False
    if enforce_cutoff and document.published_at > request.cutoff_date:
        return False
    return True


def _audit_issue(*, upgraded: int, total: int) -> ValidationIssue:
    """Return one stable informational record of the verification decision."""

    return ValidationIssue(
        issue_id=AUDIT_ISSUE_ID,
        check_name="evidence_policy",
        severity="info",
        issue_type="evidence_verification",
        message=(
            f"{upgraded} of {total} located evidence items were upgraded to "
            "verified by the explicit formal-source policy; "
            f"{total - upgraded} remain unverified."
        ),
        claim_id=None,
        evidence_id=None,
        report_section="source_filter",
        rerun_required=False,
        human_confirmation_required=False,
        status="accepted_risk",
    )


def apply_evidence_policy(
    evidence: list[Evidence],
    documents: list[SourceDocument],
    *,
    request: ResearchRequest,
    enforce_cutoff: bool = True,
) -> tuple[list[Evidence], list[ValidationIssue]]:
    """Apply the explicit rule that upgrades located evidence to verified.

    An evidence item becomes ``verified`` when its source document:

    1. carries ``review_status == "formal"``;
    2. passed the cutoff time lock (published at or before ``cutoff_date``);
    3. belongs to the requested industry.

    Company equality is intentionally not required: the analysis targets a
    company against formal peer filings of the same industry, and no
    downstream consumer compares evidence provenance to the request company.

    All other items keep their current review status, so verified-only
    consumers and the Critic's ``non_verified_evidence`` check keep guarding
    them. Input lists are never mutated; upgraded items are new copies.
    """

    documents_by_id = {document.doc_id: document for document in documents}
    upgraded_count = 0
    resolved: list[Evidence] = []

    for item in evidence:
        document = documents_by_id.get(item.doc_id)
        if item.review_status == "pending" and _is_verifiable_source(
            document,
            request,
            enforce_cutoff=enforce_cutoff,
        ):
            resolved.append(item.model_copy(update={"review_status": "verified"}))
            upgraded_count += 1
        else:
            resolved.append(item)

    return resolved, [_audit_issue(upgraded=upgraded_count, total=len(evidence))]
