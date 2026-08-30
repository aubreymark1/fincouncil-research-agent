from __future__ import annotations

import json
from pathlib import Path

from app.retrieval.cninfo import parse_cninfo_results


ROOT = Path(__file__).parents[2]


def test_cninfo_result_maps_to_search_hit():
    payload = json.loads((ROOT / "tests" / "fixtures" / "cninfo_announcements.json").read_text(encoding="utf-8"))
    hits = parse_cninfo_results(payload)

    assert hits[0].publisher == "巨潮资讯"
    assert hits[0].published_at.isoformat() == "2026-04-17"
    assert str(hits[0].source_url).startswith("https://static.cninfo.com.cn/")
    assert hits[0].source_type == "annual_report"
