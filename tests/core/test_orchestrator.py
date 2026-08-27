"""Fast unit tests for run_pipeline using injected lightweight fakes.

The production pipeline defaults to real ingestion/industry modules; these
tests inject in-memory loaders so a full orchestration pass (time lock,
extraction dispatch, evidence location, verification policy, analysis,
Critic, report rendering, three-file output) stays sub-second.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.industry.loader import load_industry_config
from app.orchestrator import run_pipeline
from app.schemas import ResearchReport, ResearchRequest, SourceDocument, TextChunk

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CUTOFF = date(2026, 8, 20)


def make_request(tmp_path: Path) -> ResearchRequest:
    output_dir = tmp_path / "outputs" / "reports" / "RUN-UNIT"
    return ResearchRequest(
        run_id="RUN-UNIT",
        company_name="示例食品公司",
        industry_id="food_beverage",
        cutoff_date=CUTOFF,
        source_manifest_path="data/manifests/food_case.csv",
        output_dir=str(output_dir),
    )


def make_document(doc_id: str, *, review_status: str) -> SourceDocument:
    return SourceDocument.model_validate(
        {
            "doc_id": doc_id,
            "title": f"文档 {doc_id}",
            "source_type": "annual_report",
            "publisher": "示例出版方",
            "local_path": "fixtures/synthetic/food_beverage/annual_report_2025.pdf",
            "published_at": "2026-04-17",
            "retrieved_at": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
            "company_name": "示例食品公司",
            "industry_id": "food_beverage",
            "trust_level": 5,
            "review_status": review_status,
            "content_hash": f"sha256:{doc_id}",
        }
    )


def fake_manifest_loader(path: str) -> list[SourceDocument]:
    del path
    return [
        make_document("DOC-UNIT-001", review_status="formal"),
        make_document("DOC-UNIT-002", review_status="background"),
    ]


def fake_text_extractor(document: SourceDocument) -> list[TextChunk]:
    suffix = "P1" if document.review_status == "formal" else "BG"
    text = (
        "报告期内公司营业收入同比增长 10%，毛利率保持稳定。"
        if document.review_status == "formal"
        else "背景资料：行业观察仅供参考。"
    )
    return [
        TextChunk(
            chunk_id=f"CHUNK-UNIT-{suffix}",
            doc_id=document.doc_id,
            text=text,
            page=1,
            section="管理层讨论与分析",
            paragraph_index=0,
            char_start=0,
            char_end=len(text),
        )
    ]


def test_run_research_writes_report_md_and_metadata_from_real_chain(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert: outputs exist and round-trip
    report_path = Path(request.output_dir) / "report.json"
    markdown_path = Path(request.output_dir) / "report.md"
    metadata_path = (
        tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json"
    )
    assert report_path.exists()
    assert markdown_path.exists() and markdown_path.stat().st_size > 0
    assert metadata_path.exists()

    saved_report = ResearchReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    assert saved_report == state.report

    saved_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert saved_metadata["status"] == "success"
    assert saved_metadata["model_provider"] == "rule-engine"
    assert saved_metadata["model_name"] == "a008-rules"
    assert saved_metadata["errors"] == []
    assert saved_metadata["module_versions"]["orchestrator"] == "v1-a008"


def test_pass_claim_cites_verified_financial_evidence_only(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert: at least one pass fact claim backed by verified financial evidence
    pass_claims = [claim for claim in state.report.claims if claim.status == "pass"]
    assert pass_claims, "expected at least one pass claim from formal-source evidence"

    index_ids = {item.evidence_id for item in state.report.evidence_index}
    cited = {
        evidence_id
        for claim in pass_claims
        for evidence_id in claim.evidence_ids
    }
    assert cited & index_ids, "pass claims must cite indexed evidence"

    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    indexed_items = [evidence_by_id[evidence_id] for evidence_id in cited & index_ids]
    assert all(item.review_status == "verified" for item in indexed_items)
    assert all(item.published_at <= CUTOFF for item in indexed_items)

    # The background-source document must never reach the evidence index.
    assert all(item.doc_id != "DOC-UNIT-002" for item in state.report.evidence_index)


def test_verification_policy_audit_issue_is_recorded(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert
    audit = [
        issue
        for issue in state.validation_issues
        if issue.check_name == "evidence_policy"
    ]
    assert len(audit) == 1


def test_unmatched_required_metric_reports_E202_without_duplicating(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    # Act
    state = run_pipeline(
        request,
        manifest_loader=fake_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert
    checklist_missing = [
        issue
        for issue in state.validation_issues
        if issue.issue_type == "missing_metric"
        and "sales_expense_rate" in issue.message
    ]
    critic_missing = [
        issue
        for issue in state.validation_issues
        if issue.issue_type == "required_metric_missing"
        and "sales_expense_rate" in issue.message
    ]
    assert checklist_missing, (
        "sales_expense_rate has no matching corpus text and must surface E202"
    )
    assert not critic_missing, "Critic E202 copies of checklist findings are dropped"


def test_empty_manifest_yields_unresolved_claims_without_evidence(tmp_path):
    # Arrange
    request = make_request(tmp_path)

    def empty_manifest_loader(path: str) -> list[SourceDocument]:
        del path
        return []

    # Act
    state = run_pipeline(
        request,
        manifest_loader=empty_manifest_loader,
        text_extractor=fake_text_extractor,
        industry_loader=load_industry_config,
    )

    # Assert: no documents -> no evidence or body claims; nodes stay honest
    assert not state.evidence
    assert not state.report.claims
    assert all(claim.claim_type == "unresolved" for claim in state.report.unresolved_items)
    assert state.report.unresolved_items
