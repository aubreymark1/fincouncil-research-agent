"""Tests for the real OpenAI-compatible HTTP transport (ADAPT-008)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from app.model import ModelConfig, ModelProviderError, openai_compatible_transport


class FakeResponse:
    def __init__(self, raw: str) -> None:
        self._raw = raw

    def read(self) -> bytes:
        return self._raw.encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_openai_transport_posts_chat_completion_and_returns_content(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse('{"choices":[{"message":{"content":"{\\"answer\\":\\"ok\\"}"}}]}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    config = ModelConfig(
        provider_name="openai-test",
        model_name="gpt-test",
        api_key="secret",
        base_url="https://example.com/v1",
        timeout_seconds=12,
    )

    result = openai_compatible_transport("hello", config)

    assert result == '{"answer":"ok"}'
    request = captured["request"]
    assert isinstance(request, urllib.request.Request)
    assert request.full_url == "https://example.com/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer secret"
    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == "gpt-test"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["timeout"] == 12


def test_openai_transport_requires_api_key() -> None:
    config = ModelConfig(provider_name="openai", model_name="m", api_key=None)

    with pytest.raises(ModelProviderError, match="E300.*API_KEY"):
        openai_compatible_transport("x", config)


def test_openai_transport_maps_http_errors_to_coded_error(monkeypatch) -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: float | None = None):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":"bad"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ModelProviderError, match="E300.*401"):
        openai_compatible_transport(
            "x",
            ModelConfig(provider_name="openai", model_name="m", api_key="k"),
        )


def test_openai_transport_rejects_missing_chat_content(monkeypatch) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda _request, **kwargs: FakeResponse("{}"),
    )

    with pytest.raises(ModelProviderError, match="E301.*chat content"):
        openai_compatible_transport(
            "x",
            ModelConfig(provider_name="openai", model_name="m", api_key="k"),
        )
