"""Allowlisted dispatch table for model-callable retrieval tools."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any
from datetime import date

from app.model.tool_types import ToolDefinition
from app.schemas import SearchQuery

from .cninfo import CNINFO_STATIC_HOSTS
from .security import validate_public_url

class ToolRegistry:
    def __init__(self, *, event_callback: Callable[[str, str, dict[str, Any]], None] | None = None) -> None:
        self._tools: dict[str, tuple[ToolDefinition, Callable[[dict[str, Any]], Any]]] = {}
        self._event_callback = event_callback

    def register(self, definition: ToolDefinition, handler: Callable[[dict[str, Any]], Any]) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        self._tools[definition.name] = (definition, handler)

    def definitions(self) -> list[ToolDefinition]:
        return [item[0] for item in self._tools.values()]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        item = self._tools.get(name)
        if item is None:
            raise ValueError(f"unknown tool: {name}")
        started = perf_counter()
        if self._event_callback is not None:
            self._event_callback(name, "start", {})
        try:
            result = item[1](arguments)
        except Exception as exc:
            if self._event_callback is not None:
                self._event_callback(name, "error", {"reason": type(exc).__name__, "duration_ms": int((perf_counter() - started) * 1000)})
            raise
        if self._event_callback is not None:
            count = len(result) if isinstance(result, list) else None
            details: dict[str, Any] = {"duration_ms": int((perf_counter() - started) * 1000)}
            if count is not None:
                details["count"] = count
            self._event_callback(name, "result", details)
        return result


def build_retrieval_registry(service: Any, *, subject: str, ticker: str | None, end_date: date, default_query: str, event_callback: Callable[[str, str, dict[str, Any]], None] | None = None) -> ToolRegistry:
    """Create the small, allowlisted tool set exposed to the research LLM."""

    registry = ToolRegistry(event_callback=event_callback)
    def fetch_authoritative(arguments: dict[str, Any]) -> dict[str, str]:
        url = str(arguments["source_url"])
        parsed = validate_public_url(url, allowed_hosts=CNINFO_STATIC_HOSTS)
        return {"source_url": url, "host": str(parsed.hostname), "status": "validated_url_only"}

    registry.register(
        ToolDefinition(
            name="search_company_filings",
            description="Search authoritative company filings before the research cutoff date.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The missing fact or filing topic to search."},
                    "ticker": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        lambda arguments: [
            hit.model_dump(mode="json")
            for hit in service.connector.search_filings(
                SearchQuery(
                    subject=subject,
                    ticker=arguments.get("ticker") or ticker,
                    query=str(arguments["query"]),
                    end_date=end_date,
                )
            )[:10]
        ],
    )
    registry.register(
        ToolDefinition(
            name="search_regulations",
            description="Search regulatory and policy notices that may affect the research question.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        lambda arguments: [
            hit.model_dump(mode="json")
            for hit in service.connector.search_filings(
                SearchQuery(subject=subject, query=str(arguments["query"]), end_date=end_date, categories=["regulation"])
            )
            if hit.source_type == "regulation"
        ][:10],
    )
    registry.register(
        ToolDefinition(
            name="fetch_authoritative_document",
            description="Validate that a document URL is from an allowlisted authoritative source.",
            input_schema={
                "type": "object",
                "properties": {"source_url": {"type": "string", "format": "uri"}},
                "required": ["source_url"],
                "additionalProperties": False,
            },
        ),
        fetch_authoritative,
    )
    registry.register(
        ToolDefinition(
            name="inspect_evidence_gap",
            description="Explain which research metrics are not covered by the current evidence pool.",
            input_schema={
                "type": "object",
                "properties": {"metric_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["metric_ids"],
                "additionalProperties": False,
            },
        ),
        lambda arguments: {
            "query": default_query,
            "missing_metric_ids": list(arguments.get("metric_ids", [])),
            "next_step": "补充权威公告后重新建立 Evidence",
        },
    )
    return registry
