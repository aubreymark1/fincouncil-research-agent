from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from app.schemas import Evidence, ReportBlock, ResearchReport
from evaluation.narrative_metrics import evaluate_narrative


ROOT = Path(__file__).parents[2]
GOLD = ROOT / "fixtures" / "evaluation" / "mini_bank_gold.json"


def make_evidence(*, review_status: str = "verified") -> Evidence:
    return Evidence(
        evidence_id="EV-MINI-BANK-METRICS",
        doc_id="DOC-MINI-BANK-001",
        chunk_id="CHUNK-MINI-BANK-001",
        fact_text=(
            "净利息收益率为 1.28%，客户贷款及垫款总额较上年末增长 7.5%；"
            "不良贷款率为 1.31%，拨备覆盖率为 213.60%，资本充足率为 18.76%。"
        ),
        quote=(
            "净利息收益率为 1.28%，客户贷款及垫款总额较上年末增长 7.5%；"
            "不良贷款率为 1.31%，拨备覆盖率为 213.60%，资本充足率为 18.76%。"
        ),
        published_at=date(2026, 3, 28),
        page=None,
        section="指标披露",
        locator="DOC-MINI-BANK-001, section 指标披露",
        company_name="实验工商银行",
        industry_id="banking",
        evidence_type="financial",
        confidence=0.9,
        review_status=review_status,
    )


def make_report(evidence: Evidence) -> ResearchReport:
    return ResearchReport(
        run_id="RUN-NARRATIVE-METRICS",
        company_name="实验工商银行",
        industry_id="banking",
        cutoff_date=date(2026, 8, 20),
        summary=[],
        narrative=[
            ReportBlock(
                section="核心判断",
                text=evidence.fact_text,
                evidence_ids=[evidence.evidence_id],
            )
        ],
        claims=[],
        risks=[],
        unresolved_items=[],
        evidence_index=[evidence],
        validation_issues=[],
        generated_at=datetime.now(timezone.utc),
        report_version="test",
    )


def test_evaluate_narrative_scores_text_and_verified_citations() -> None:
    result = evaluate_narrative(make_report(make_evidence()), str(GOLD))

    assert result["key_factor_coverage_rate"] == 1.0
    assert result["evidence_validity_rate"] == 1.0
    assert result["citation_location_accuracy_rate"] == 1.0
    assert result["cutoff_violation_count"] == 0.0


def test_evaluate_narrative_rejects_pending_citations() -> None:
    result = evaluate_narrative(
        make_report(make_evidence(review_status="pending")),
        str(GOLD),
    )

    assert result["key_factor_coverage_rate"] == 1.0
    assert result["evidence_validity_rate"] == 0.0
