from __future__ import annotations

import pytest

from backend.db import RunStore


def make_store(tmp_path):
    store = RunStore(tmp_path / "run-events.db")
    store.init()
    store.create_run(run_id="RUN-WB-EVENTS", case_id="food_main", llm_enabled=True)
    return store


def test_run_events_are_ordered_and_public_details_are_allowlisted(tmp_path):
    store = make_store(tmp_path)

    first = store.append_event(
        "RUN-WB-EVENTS",
        kind="tool_start",
        title="检索公告",
        summary="开始检索",
        tool_name="search_company_filings",
        public_details={"query": "600519"},
    )
    second = store.append_event(
        "RUN-WB-EVENTS",
        kind="tool_result",
        title="检索完成",
        summary="找到 4 份资料",
        tool_name="search_company_filings",
        status="success",
        duration_ms=840,
        public_details={"count": 4},
    )

    events = store.list_events("RUN-WB-EVENTS", after_sequence=0)
    assert [event["sequence"] for event in events] == [first["sequence"], second["sequence"]]
    assert events[1]["duration_ms"] == 840
    assert "api_key" not in str(events)


def test_run_events_reject_sensitive_public_detail_keys(tmp_path):
    store = make_store(tmp_path)

    with pytest.raises(ValueError, match="public detail key"):
        store.append_event(
            "RUN-WB-EVENTS",
            kind="error",
            title="失败",
            summary="请求失败",
            public_details={"api_key": "secret"},
        )


def test_run_events_resume_after_sequence(tmp_path):
    store = make_store(tmp_path)
    store.append_event("RUN-WB-EVENTS", kind="stage", title="准备研究", summary="完成")
    store.append_event("RUN-WB-EVENTS", kind="stage", title="定位证据", summary="完成")

    events = store.list_events("RUN-WB-EVENTS", after_sequence=1)
    assert len(events) == 1
    assert events[0]["title"] == "定位证据"
