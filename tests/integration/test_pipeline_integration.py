"""End-to-end integration tests for the real B ingestion + C industry chain.

These tests exercise run_pipeline with its production defaults (real
manifest/PDF/HTML loading, chunking, evidence location, verification policy,
analysis nodes, Critic, and three-file report output) against the small
deterministic synthetic PDFs in ``fixtures/synthetic``. Real annual reports
under ``data/raw`` stay out of CI and are validated manually via
``scripts/run_case.py``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.main import run_research
from app.model import InMemoryCache, ModelConfig, ModelProvider, ModelProviderError
from app.orchestrator import run_pipeline
from app.schemas import ResearchReport, ResearchRequest, SourceDocument
from app.ingestion.manifest import ManifestError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CUTOFF = "2026-08-20"

MANIFEST_HEADER = (
    "doc_id,title,source_type,publisher,source_url,local_path,published_at,"
    "event_date,retrieved_at,company_name,industry_id,trust_level,review_status"
)


def make_request(tmp_path: Path, manifest_path: Path, *, industry: str) -> ResearchRequest:
    return ResearchRequest(
        run_id="RUN-INT",
        company_name="示例食品公司" if industry == "food_beverage" else "示例银行",
        industry_id=industry,
        cutoff_date=date.fromisoformat(CUTOFF),
        source_manifest_path=str(manifest_path),
        output_dir=str(tmp_path / "outputs" / "reports" / "RUN-INT"),
    )


def write_manifest(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join([MANIFEST_HEADER, *rows]) + "\n", encoding="utf-8")


def row(
    doc_id: str,
    local_path: str,
    *,
    source_type: str,
    publisher: str,
    published_at: str | None,
    company: str,
    industry: str,
    review_status: str = "formal",
) -> str:
    fields = [
        doc_id,
        f"{company}{source_type}",
        source_type,
        publisher,
        "",
        local_path,
        published_at or "",
        "",
        "2026-08-20T10:00:00+08:00",
        company,
        industry,
        "5",
        review_status,
    ]
    return ",".join(fields)


FOOD_PDF_DIR = "fixtures/synthetic/food_beverage"
BANK_PDF_DIR = "fixtures/synthetic/banking"


@pytest.fixture()
def food_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "food_integration.csv"
    html_article = tmp_path / "channel_update.html"
    html_article.write_text(
        "<html><head><title>渠道动态</title></head><body>"
        "<h1>渠道更新公告</h1><p>经销商反馈渠道库存保持健康。</p>"
        "</body></html>",
        encoding="utf-8",
    )
    write_manifest(
        manifest,
        [
            row(
                "DOC-INT-001",
                f"{FOOD_PDF_DIR}/annual_report_2025.pdf",
                source_type="annual_report",
                publisher="示例食品公司",
                published_at="2026-03-30",
                company="示例食品公司",
                industry="food_beverage",
            ),
            row(
                "DOC-INT-002",
                f"{FOOD_PDF_DIR}/interim_report_2025.pdf",
                source_type="interim_report",
                publisher="示例食品公司",
                published_at="2025-08-29",
                company="示例食品公司",
                industry="food_beverage",
            ),
            row(
                "DOC-INT-003",
                f"{FOOD_PDF_DIR}/food_safety_policy.pdf",
                source_type="policy",
                publisher="行业监管部门",
                published_at="2026-02-11",
                company="示例食品公司",
                industry="food_beverage",
            ),
            row(
                "DOC-INT-004",
                str(html_article),
                source_type="company_release",
                publisher="示例食品公司",
                published_at="2026-05-06",
                company="示例食品公司",
                industry="food_beverage",
            ),
            row(
                "DOC-INT-RT1",
                f"{FOOD_PDF_DIR}/industry_news.pdf",
                source_type="news",
                publisher="行业媒体",
                published_at="2026-01-15",
                company="示例食品公司",
                industry="food_beverage",
                review_status="red_team",
            ),
        ],
    )
    return manifest


@pytest.fixture()
def banking_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "banking_integration.csv"
    write_manifest(
        manifest,
        [
            row(
                "DOC-INT-B01",
                f"{BANK_PDF_DIR}/annual_report_2025.pdf",
                source_type="annual_report",
                publisher="示例银行",
                published_at="2026-03-30",
                company="示例银行",
                industry="banking",
            ),
            row(
                "DOC-INT-B02",
                f"{BANK_PDF_DIR}/credit_quality_notice.pdf",
                source_type="announcement",
                publisher="示例银行",
                published_at="2026-04-02",
                company="示例银行",
                industry="banking",
            ),
        ],
    )
    return manifest


def test_food_pipeline_runs_end_to_end_with_verified_evidence(tmp_path, food_manifest):
    # Arrange
    request = make_request(tmp_path, food_manifest, industry="food_beverage")

    # Act
    state = run_pipeline(request)

    # Assert: three artefacts written and metadata reflects the real chain
    assert (Path(request.output_dir) / "report.json").exists()
    assert (Path(request.output_dir) / "report.md").stat().st_size > 0
    metadata = json.loads(
        (tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert metadata["status"] == "success"
    assert metadata["model_name"] == "a008-rules"
    assert metadata["errors"] == []

    saved_report = ResearchReport.model_validate_json(
        (Path(request.output_dir) / "report.json").read_text(encoding="utf-8")
    )
    assert saved_report.industry_id == "food_beverage"

    # At least one pass claim cites verified financial evidence.
    pass_claims = [claim for claim in saved_report.claims if claim.status == "pass"]
    assert pass_claims, "formal synthetic filings must yield at least one pass claim"
    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    for claim in pass_claims:
        for evidence_id in claim.evidence_ids:
            assert evidence_by_id[evidence_id].review_status == "verified"

    # Index only holds verified evidence of time-lock-passed sources.
    index_ids = {item.evidence_id for item in saved_report.evidence_index}
    red_team_ids = {
        item.evidence_id for item in state.evidence if item.doc_id == "DOC-INT-RT1"
    }
    assert not index_ids & red_team_ids
    assert all(item.published_at <= request.cutoff_date for item in saved_report.evidence_index)


def test_food_pipeline_surfaces_E202_once_per_uncovered_metric(tmp_path, food_manifest):
    # Arrange
    request = make_request(tmp_path, food_manifest, industry="food_beverage")

    # Act
    state = run_pipeline(request)

    # Assert: sales_expense_rate has no matching corpus text; checklist E202 is
    # authoritative and the Critic duplicate is dropped by the orchestrator.
    missing_metric_issues = [
        issue
        for issue in state.validation_issues
        if issue.issue_type == "missing_metric"
        and "sales_expense_rate" in issue.message
    ]
    critic_duplicates = [
        issue
        for issue in state.validation_issues
        if issue.issue_type == "required_metric_missing"
        and "sales_expense_rate" in issue.message
    ]
    assert len(missing_metric_issues) == 1
    assert not critic_duplicates


def test_bank_pipeline_loads_different_industry_config(tmp_path, banking_manifest):
    # Arrange
    request = make_request(tmp_path, banking_manifest, industry="banking")

    # Act
    state = run_pipeline(request)
    bank_keywords = {"净息差", "不良", "资本充足率", "拨备"}

    # Assert
    assert state.report.industry_id == "banking"
    located_texts = "\n".join(item.fact_text for item in state.evidence)
    assert any(keyword in located_texts for keyword in bank_keywords), (
        "synthetic banking filings contain at least one configured metric keyword"
    )


def test_llm_mode_rejects_evidence_not_sent_to_node(tmp_path, food_manifest):
    # Arrange
    request = make_request(tmp_path, food_manifest, industry="food_beverage")

    def bad_claim(**updates: object) -> dict:
        payload = {
            "claim_id": "CL-LLM-BAD-001",
            "text": "LLM 引用了未发送给节点的证据。",
            "claim_type": "fact",
            "risk_severity": None,
            "evidence_ids": ["EV-NOPE-001"],
            "calculation": None,
            "confidence": 0.9,
            "industry_metric_ids": ["revenue_growth"],
            "status": "pass",
        }
        payload.update(updates)
        return payload

    def transport(prompt: str, _config: ModelConfig) -> dict:
        if "行业 Critic 提示词" in prompt:
            return {"issues": []}
        if "新闻与政策分析提示词" in prompt:
            return {
                "claims": [
                    bad_claim(claim_type="change", status="review")
                ]
            }
        if "风险分析提示词" in prompt:
            return {
                "claims": [
                    bad_claim(
                        claim_type="unresolved",
                        status="review",
                        evidence_ids=[],
                        industry_metric_ids=[],
                    )
                ]
            }
        return {"claims": [bad_claim()]}

    provider = ModelProvider(ModelConfig(max_retries=0), transport=transport)

    # Act / Assert: node-level evidence isolation rejects the bad ID.
    with pytest.raises(ModelProviderError, match="current batch"):
        run_pipeline(request, model_provider=provider)

    metadata_path = tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["errors"][0].startswith("E301 module=agents.llm")


def test_llm_failure_writes_failed_run_metadata(tmp_path, food_manifest):
    # Arrange
    request = make_request(tmp_path, food_manifest, industry="food_beverage")

    def transport(_prompt: str, _config: ModelConfig) -> dict:
        raise ModelProviderError("E300 module=model.transport: test failure")

    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=transport,
        cache=InMemoryCache(),
    )

    # Act / Assert
    with pytest.raises(ModelProviderError, match="E300"):
        run_pipeline(request, model_provider=provider)

    metadata_path = tmp_path / "outputs" / "logs" / request.run_id / "run_metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["errors"][0].startswith("E300 module=model: transport failed")
    assert metadata["input_hashes"]["request"].startswith("sha256:")
    assert metadata["module_versions"]["cache"] == "v1-json"


def test_missing_manifest_fails_fast_with_manifest_error(tmp_path):
    # Arrange
    missing_path = tmp_path / "does_not_exist.csv"
    request = make_request(tmp_path, missing_path, industry="food_beverage")

    # Act / Assert
    with pytest.raises(ManifestError, match="E100"):
        run_research(request)


def test_unknown_source_format_raises_clear_error(tmp_path):
    # Arrange
    binary_doc_path = tmp_path / "annual_report_2025.docx"
    binary_doc_path.write_bytes(b"not a pdf")
    manifest = tmp_path / "bad_format.csv"
    write_manifest(
        manifest,
        [
            row(
                "DOC-INT-BAD",
                str(binary_doc_path),
                source_type="annual_report",
                publisher="示例食品公司",
                published_at="2026-03-30",
                company="示例食品公司",
                industry="food_beverage",
            ),
        ],
    )

    def fake_loader(path: str) -> list[SourceDocument]:
        del path
        from datetime import datetime, timezone

        return [
            SourceDocument.model_validate(
                {
                    "doc_id": "DOC-INT-BAD",
                    "title": "bad format doc",
                    "source_type": "annual_report",
                    "publisher": "示例食品公司",
                    "local_path": str(binary_doc_path),
                    "published_at": "2026-03-30",
                    "retrieved_at": datetime(2026, 8, 20, tzinfo=timezone.utc).isoformat(),
                    "company_name": "示例食品公司",
                    "industry_id": "food_beverage",
                    "trust_level": 5,
                    "review_status": "formal",
                    "content_hash": "sha256:bad",
                }
            )
        ]

    request = make_request(tmp_path, manifest, industry="food_beverage")

    # Act / Assert
    with pytest.raises(ValueError, match="E100"):
        run_pipeline(
            request,
            manifest_loader=fake_loader,
        )
