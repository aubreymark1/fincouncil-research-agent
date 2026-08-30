from __future__ import annotations

import pytest

from app.model import ModelConfig, ModelProvider, ModelProviderError
from app.model.tool_types import ToolCall, ToolDefinition, ToolTurn


def test_provider_executes_whitelisted_tool_then_returns_json():
    calls: list[tuple[str, dict]] = []
    turns = iter([
        ToolTurn(tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"ticker": "600519"})]),
        ToolTurn(content='{"answer": "done"}'),
    ])

    def transport(_messages, _tools, _config):
        return next(turns)

    provider = ModelProvider(ModelConfig(max_retries=0), tool_transport=transport)
    result = provider.run_with_tools(
        [{"role": "user", "content": "lookup"}],
        [ToolDefinition(name="lookup", description="look up", input_schema={"type": "object"})],
        lambda name, arguments: calls.append((name, arguments)) or {"count": 1},
    )

    assert calls == [("lookup", {"ticker": "600519"})]
    assert result == {"answer": "done"}


def test_provider_rejects_unknown_tool():
    def transport(_messages, _tools, _config):
        return ToolTurn(tool_calls=[ToolCall(id="call-1", name="unknown", arguments={})])

    provider = ModelProvider(ModelConfig(max_retries=0), tool_transport=transport)
    with pytest.raises(ModelProviderError, match="unknown tool"):
        provider.run_with_tools([], [], lambda _name, _arguments: {})


def test_provider_stops_after_tool_call_limit():
    def transport(_messages, _tools, _config):
        return ToolTurn(tool_calls=[ToolCall(id="call-1", name="lookup", arguments={})])

    provider = ModelProvider(ModelConfig(max_retries=0), tool_transport=transport)
    with pytest.raises(ModelProviderError, match="tool call limit"):
        provider.run_with_tools(
            [],
            [ToolDefinition(name="lookup", description="look up", input_schema={"type": "object"})],
            lambda _name, _arguments: {},
            max_tool_calls=2,
        )
