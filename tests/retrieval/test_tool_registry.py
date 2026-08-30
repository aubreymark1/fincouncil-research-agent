from __future__ import annotations

import pytest

from app.model.tool_types import ToolDefinition
from app.retrieval.tool_registry import ToolRegistry


def test_registry_dispatches_only_registered_tools():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="lookup", description="lookup", input_schema={"type": "object"}),
        lambda arguments: {"ticker": arguments["ticker"]},
    )

    assert registry.dispatch("lookup", {"ticker": "600519"}) == {"ticker": "600519"}
    assert registry.definitions()[0].name == "lookup"


def test_registry_rejects_unknown_tool():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="unknown tool"):
        registry.dispatch("search", {})


def test_default_registry_validates_fetch_url(monkeypatch):
    from datetime import date
    from app.retrieval.service import RetrievalService
    from app.retrieval.tool_registry import build_retrieval_registry

    monkeypatch.setattr("app.retrieval.security.resolve_host_ips", lambda _host: ["1.1.1.1"])
    service = RetrievalService("outputs", connector=type("C", (), {"search_filings": lambda self, query: []})())
    registry = build_retrieval_registry(
        service,
        subject="测试公司",
        ticker=None,
        end_date=date(2026, 8, 20),
        default_query="公告",
    )

    assert registry.dispatch("fetch_authoritative_document", {"source_url": "https://static.cninfo.com.cn/report.pdf"})["status"] == "validated_url_only"
    with pytest.raises(ValueError):
        registry.dispatch("fetch_authoritative_document", {"source_url": "https://example.com/report.pdf"})
