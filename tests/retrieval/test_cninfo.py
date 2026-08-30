from __future__ import annotations

import json
from pathlib import Path

from app.retrieval.cninfo import parse_cninfo_results
from app.retrieval.cninfo import CninfoConnector
from app.schemas import SearchQuery


ROOT = Path(__file__).parents[2]


def test_cninfo_result_maps_to_search_hit():
    payload = json.loads((ROOT / "tests" / "fixtures" / "cninfo_announcements.json").read_text(encoding="utf-8"))
    hits = parse_cninfo_results(payload)

    assert hits[0].publisher == "巨潮资讯"
    assert hits[0].published_at.isoformat() == "2026-04-17"
    assert str(hits[0].source_url).startswith("https://static.cninfo.com.cn/")
    assert hits[0].source_type == "annual_report"
    assert "<em>" not in hits[0].title


def test_cninfo_search_uses_subject_and_question(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"announcements": []}'

    def fake_urlopen(request, timeout):
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    CninfoConnector(timeout_seconds=7).search_filings(SearchQuery(subject="贵州茅台", ticker="600519", query="库存", end_date="2026-08-20"))
    assert "searchkey=600519" in captured["body"]
    assert "stock=" in captured["body"]
    assert captured["timeout"] == 7
