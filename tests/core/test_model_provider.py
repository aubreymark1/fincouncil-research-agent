"""Tests for the SDK-neutral A-003 ModelProvider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.model import InMemoryCache, JsonFileCache, ModelConfig, ModelProvider, ModelProviderError


class ExampleOutput(BaseModel):
    answer: str


def test_model_config_reads_environment_and_bounds_retries() -> None:
    config = ModelConfig.from_env(
        {
            "FINCOUNCIL_MODEL_PROVIDER": "fixture-provider",
            "FINCOUNCIL_MODEL_NAME": "fixture-model",
            "FINCOUNCIL_MODEL_API_KEY": "fixture-only",
            "FINCOUNCIL_MODEL_TEMPERATURE": "0.4",
            "FINCOUNCIL_MODEL_MAX_RETRIES": "99",
            "FINCOUNCIL_MODEL_TIMEOUT_SECONDS": "12",
        }
    )

    assert config.provider_name == "fixture-provider"
    assert config.model_name == "fixture-model"
    assert config.temperature == 0.4
    assert config.max_retries == 5
    assert config.timeout_seconds == 12
    assert "fixture-only" not in repr(config)


def test_temperature_defaults_to_zero() -> None:
    assert ModelConfig.from_env({}).temperature == 0.0


def test_structured_output_is_validated_and_cached() -> None:
    calls: list[str] = []

    def transport(prompt: str, config: ModelConfig) -> str:
        calls.append(prompt)
        assert config.temperature == 0.0
        return '{"answer": "ok"}'

    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=transport,
        cache=InMemoryCache(),
    )

    first = provider.generate_json("return an answer", response_model=ExampleOutput)
    second = provider.generate_json("return an answer", response_model=ExampleOutput)

    assert isinstance(first, ExampleOutput)
    assert first.answer == "ok"
    assert second == first
    assert calls == ["return an answer"]


def test_json_fenced_response_is_supported() -> None:
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: "```json\n{\"answer\": \"ok\"}\n```",
    )

    result = provider.generate("return JSON")

    assert result == {"answer": "ok"}


def test_transport_failures_are_retried_with_a_hard_limit() -> None:
    attempts: list[int] = []

    def transport(_prompt: str, _config: ModelConfig) -> dict[str, str]:
        attempts.append(1)
        raise RuntimeError("transport failed")

    provider = ModelProvider(
        ModelConfig(max_retries=2),
        transport=transport,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(ModelProviderError, match="E300.*3 attempts"):
        provider.generate_json("return JSON")

    assert len(attempts) == 3


def test_invalid_structured_output_is_retried_and_then_rejected() -> None:
    attempts: list[int] = []

    def transport(_prompt: str, _config: ModelConfig) -> str:
        attempts.append(1)
        return "not-json"

    provider = ModelProvider(
        ModelConfig(max_retries=1),
        transport=transport,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(ModelProviderError, match="E300.*2 attempts"):
        provider.generate_json("return JSON", response_model=ExampleOutput)

    assert len(attempts) == 2


def test_json_file_cache_round_trips_without_credentials(tmp_path: Path) -> None:
    cache_path = tmp_path / "model-cache.json"
    cache = JsonFileCache(cache_path)
    cache.set("key", {"answer": "cached"})

    assert cache.get("key") == {"answer": "cached"}
    assert "fixture-only" not in cache_path.read_text(encoding="utf-8")
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {"key": {"answer": "cached"}}


def test_missing_transport_has_coded_error() -> None:
    provider = ModelProvider(ModelConfig())

    with pytest.raises(ModelProviderError, match="E300.*no transport"):
        provider.generate_json("return JSON")
