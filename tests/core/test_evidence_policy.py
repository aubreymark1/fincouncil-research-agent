"""Unit tests for the deterministic evidence verification policy."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.orchestrator.evidence_policy import (
    AUDIT_ISSUE_ID,
    apply_evidence_policy,
)
from app.schemas import Evidence, ResearchRequest, SourceDocument

CUTOFF = date(2026, 8, 20)


def make_request(industry_id: str = "food_beverage") -> ResearchRequest:
    return ResearchRequest(
        run_id="RUN-POLICY",
        company_name="示例食品公司",
        industry_id=industry_id,
        cutoff_date=CUTOFF,
        source_manifest_path="data/manifests/food_case.csv",
        output_dir="outputs/reports/RUN-POLICY",
    )


def make_document(
    doc_id: str,
    *,
    review_status: str = "formal",
    industry_id: str | None = "food_beverage",
    published_at: date | None = CUTOFF,
) -> SourceDocument:
    return SourceDocument.model_validate(
        {
            "doc_id": doc_id,
            "title": "示例年报",
            "source_type": "annual_report",
            "publisher": "示例出版方",
            "local_path": "fixtures/synthetic/food_beverage/annual_report_2025.pdf",
            "published_at": published_at.isoformat() if published_at else None,
            "retrieved_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
            "company_name": "示例食品公司",
            "industry_id": industry_id,
            "trust_level": 5,
            "review_status": review_status,
            "content_hash": f"sha256:{doc_id}",
        }
    )


def make_evidence(evidence_id: str, *, doc_id: str = "DOC-FOOD-001", **updates: object) -> Evidence:
    payload: dict[str, object] = {
        "evidence_id": evidence_id,
        "doc_id": doc_id,
        "chunk_id": "CHUNK-FOOD-001-P1",
        "fact_text": "报告期内公司营业收入同比增长。",
        "quote": "报告期内公司营业收入同比增长。",
        "published_at": CUTOFF,
        "page": 1,
        "locator": "page 1, chunk CHUNK-FOOD-001-P1",
        "company_name": "示例食品公司",
        "industry_id": "food_beverage",
        "evidence_type": "financial",
        "confidence": 0.5,
        "review_status": "pending",
    }
    payload.update(updates)
    return Evidence.model_validate(payload)


def test_formal_industry_matched_source_upgrades_pending_to_verified():
    # Arrange
    request = make_request()
    document = make_document("DOC-FOOD-001")
    item = make_evidence("EV-FOOD-001-FINANCIAL-ABCD1234-0")

    # Act
    resolved, issues = apply_evidence_policy([item], [document], request=request)

    # Assert
    assert resolved[0].review_status == "verified"
    assert resolved[0] is not item


def test_background_and_red_team_sources_stay_pending():
    # Arrange
    request = make_request()
    background_doc = make_document("DOC-BG-1", review_status="background")
    red_team_doc = make_document("DOC-RT-1", review_status="red_team")
    items = [
        make_evidence("EV-BG-1", doc_id="DOC-BG-1"),
        make_evidence("EV-RT-1", doc_id="DOC-RT-1"),
    ]

    # Act
    resolved, _ = apply_evidence_policy(items, [background_doc, red_team_doc], request=request)

    # Assert
    assert all(item.review_status == "pending" for item in resolved)


def test_rejected_and_undated_statuses_stay_pending():
    # Arrange
    request = make_request()
    rejected_doc = make_document("DOC-RJ-1", review_status="rejected")
    pending_date_doc = make_document("DOC-PD-1", review_status="pending_date")
    items = [
        make_evidence("EV-RJ-1", doc_id="DOC-RJ-1"),
        make_evidence("EV-PD-1", doc_id="DOC-PD-1"),
    ]

    # Act
    resolved, _ = apply_evidence_policy(items, [rejected_doc, pending_date_doc], request=request)

    # Assert
    assert all(item.review_status == "pending" for item in resolved)


def test_other_industry_source_stays_pending():
    # Arrange
    request = make_request()
    banking_doc = make_document("DOC-BANK-1", industry_id="banking")

    # Act
    resolved, _ = apply_evidence_policy(
        [make_evidence("EV-BANK-1", doc_id="DOC-BANK-1")],
        [banking_doc],
        request=request,
    )

    # Assert
    assert resolved[0].review_status == "pending"


def test_post_cutoff_published_at_stays_pending_even_if_passed_in():
    # Arrange
    request = make_request()
    late_doc = make_document("DOC-LATE-1", published_at=date(2026, 8, 25))

    # Act
    resolved, _ = apply_evidence_policy(
        [make_evidence("EV-LATE-1", doc_id="DOC-LATE-1")],
        [late_doc],
        request=request,
    )

    # Assert
    assert resolved[0].review_status == "pending"


def test_orphan_doc_reference_stays_pending():
    # Arrange
    request = make_request()
    orphan = make_evidence("EV-ORPHAN-1", doc_id="DOC-GHOST")

    # Act
    resolved, _ = apply_evidence_policy([orphan], [], request=request)

    # Assert
    assert resolved[0].review_status == "pending"


def test_already_verified_items_are_left_alone():
    # Arrange
    request = make_request()
    document = make_document("DOC-FOOD-001")
    verified = make_evidence("EV-FOOD-V", review_status="verified")

    # Act
    resolved, issues = apply_evidence_policy([verified], [document], request=request)

    # Assert
    assert resolved[0] is verified


def test_audit_issue_reports_zero_upgrades_when_pool_empty():
    # Arrange
    request = make_request()

    # Act
    _, issues = apply_evidence_policy([], [], request=request)

    # Assert
    assert len(issues) == 1
    assert issues[0].issue_id == AUDIT_ISSUE_ID
    assert "0 of 0" in issues[0].message


def test_audit_issue_reports_mixed_upgrade_counts():
    # Arrange
    request = make_request()
    formal_doc = make_document("DOC-FOOD-001")
    red_team_doc = make_document("DOC-RT-1", review_status="red_team")
    pool = [
        make_evidence("EV-A", doc_id="DOC-FOOD-001"),
        make_evidence("EV-B", doc_id="DOC-RT-1"),
    ]

    # Act
    resolved, issues = apply_evidence_policy(pool, [formal_doc, red_team_doc], request=request)

    # Assert
    assert sum(item.review_status == "verified" for item in resolved) == 1
    assert "1 of 2" in issues[0].message
