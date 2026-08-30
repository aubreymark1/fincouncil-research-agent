from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.retrieval.service import RetrievalService
from app.ingestion.manifest import load_manifest
from app.schemas import SearchHit, SearchQuery


def test_service_writes_manifest_with_required_source_fields(tmp_path: Path):
    hit = SearchHit(
        title="贵州茅台2025年年度报告",
        source_url="https://static.cninfo.com.cn/finalpage/2026-04-17/report.PDF",
        publisher="巨潮资讯",
        published_at=date(2026, 4, 17),
        source_type="annual_report",
    )
    def download(_hit, destination: Path) -> Path:
        destination.write_bytes(b"%PDF-1.7 fixture")
        return destination

    service = RetrievalService(
        tmp_path,
        connector=type("Connector", (), {"search_filings": lambda self, query: [hit]})(),
        downloader=download,
    )
    query = SearchQuery(subject="贵州茅台", ticker="600519", query="年度报告", end_date=date(2026, 8, 20))

    manifest_path, hits = service.prepare_manifest("RUN-WB-ONLINE", query)

    assert len(hits) == 1
    records = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert records[0]["published_at"] == "2026-04-17"
    assert records[0]["review_status"] == "formal"
    assert records[0]["trust_level"] == 5
    assert load_manifest(str(manifest_path))[0].doc_id == "DOC-ONLINE-001"
