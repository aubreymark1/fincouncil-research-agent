from __future__ import annotations

from datetime import date
from pathlib import Path

from app.ingestion.manifest import load_manifest
from app.model import ModelConfig, ModelProvider, ToolCall, ToolTurn
from app.orchestrator import run_pipeline
from app.retrieval.service import RetrievalService
from app.retrieval.tool_registry import build_retrieval_registry
from app.schemas import Evidence, ResearchRequest, SearchHit, SearchQuery, TextChunk


def test_unlisted_company_runs_through_retrieval_manifest_and_tool_call(tmp_path: Path, monkeypatch):
    hit = SearchHit(
        title="测试公司2025年年度报告",
        source_url="https://static.cninfo.com.cn/finalpage/2026-04-17/test.PDF",
        publisher="巨潮资讯",
        published_at=date(2026, 4, 17),
        source_type="annual_report",
    )

    def download(_hit: SearchHit, destination: Path) -> Path:
        destination.write_bytes(b"%PDF-1.7 online fixture")
        return destination

    service = RetrievalService(
        tmp_path / "outputs",
        connector=type("Connector", (), {"search_filings": lambda self, query: [hit]})(),
        downloader=download,
    )
    query = SearchQuery(
        subject="测试公司",
        ticker="600519",
        query="收入质量和主要风险",
        end_date=date(2026, 8, 20),
    )
    manifest_path, _ = service.prepare_manifest("RUN-WB-ONLINE-001", query)
    assert load_manifest(str(manifest_path))[0].title == "测试公司2025年年度报告"

    evidence_id = "EV-ONLINE-001"
    calls = iter([
        ToolTurn(tool_calls=[ToolCall(id="call-1", name="inspect_evidence_gap", arguments={"metric_ids": ["business_outlook"]})]),
        ToolTurn(content='{"blocks":[{"section":"核心判断","segments":[{"segment_id":"SEG-ONLINE-001","text":"测试公司披露经营变化。","evidence_ids":["EV-ONLINE-001"],"claim_type":"fact","status":"pass"}]}]}'),
    ])

    def transport(prompt: str, _config: ModelConfig) -> dict:
        if "行业 Critic 提示词" in prompt:
            return {"issues": []}
        if "新闻与政策分析提示词" in prompt or "风险分析提示词" in prompt:
            return {"claims": []}
        return {
            "claims": [{
                "claim_id": "CL-ONLINE-001",
                "text": "测试公司披露经营变化。",
                "claim_type": "fact",
                "risk_severity": None,
                "evidence_ids": [evidence_id],
                "calculation": None,
                "confidence": 0.8,
                "industry_metric_ids": ["business_outlook"],
                "status": "pass",
            }]
        }

    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=transport,
        tool_transport=lambda _messages, _tools, _config: next(calls),
    )
    tool_events = []
    registry = build_retrieval_registry(
        service,
        subject="测试公司",
        ticker="600519",
        end_date=date(2026, 8, 20),
        default_query=query.query,
        event_callback=lambda name, phase, details: tool_events.append((name, phase, details)),
    )
    request = ResearchRequest(
        run_id="RUN-WB-ONLINE-001",
        company_name="测试公司",
        ticker="600519",
        industry_id="general",
        research_question=query.query,
        cutoff_date=date(2026, 8, 20),
        source_manifest_path=str(manifest_path),
        output_dir=str(tmp_path / "outputs" / "reports" / "RUN-WB-ONLINE-001"),
    )

    def extract(_document):
        return [TextChunk(
            chunk_id="CHUNK-ONLINE-001",
            doc_id="DOC-ONLINE-001",
            text="测试公司经营变化。",
            page=1,
            paragraph_index=0,
            char_start=0,
            char_end=9,
        )]

    monkeypatch.setattr(
        "app.orchestrator.graph._locate_config_evidence",
        lambda **_kwargs: [Evidence(
            evidence_id=evidence_id,
            doc_id="DOC-ONLINE-001",
            chunk_id="CHUNK-ONLINE-001",
            fact_text="测试公司经营变化。",
            quote="测试公司经营变化。",
            published_at="2026-04-17",
            page=1,
            section=None,
            locator="page 1",
            company_name="测试公司",
            industry_id="general",
            evidence_type="financial",
            confidence=0.9,
            review_status="verified",
        )],
    )

    state = run_pipeline(
        request,
        model_provider=provider,
        tool_registry=registry,
        text_extractor=extract,
    )

    assert state.report is not None
    assert state.report.narrative[0].segments[0].evidence_ids == [evidence_id]
    assert [phase for _name, phase, _details in tool_events] == ["start", "result"]
