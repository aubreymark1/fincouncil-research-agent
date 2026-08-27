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

    with pytest.raises(ModelProviderError, match="E301.*2 attempts"):
        provider.generate_json("return JSON", response_model=ExampleOutput)

    assert len(attempts) == 2


def test_has_cache_property_reflects_configured_cache() -> None:
    cached = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: '{"answer": "ok"}',
        cache=InMemoryCache(),
    )
    uncached = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: '{"answer": "ok"}',
    )

    assert cached.cache is not None
    assert cached.has_cache is True
    assert uncached.cache is None
    assert uncached.has_cache is False


def test_model_provider_error_exposes_code() -> None:
    error = ModelProviderError("E301 module=model.transport: response missing chat content")
    assert error.code == "E301"


def test_transport_e301_is_preserved_after_retries() -> None:
    attempts: list[int] = []

    def transport(_prompt: str, _config: ModelConfig) -> str:
        attempts.append(1)
        raise ModelProviderError(
            "E301 module=model.transport: response missing chat content"
        )

    provider = ModelProvider(
        ModelConfig(max_retries=1),
        transport=transport,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(ModelProviderError, match=r"E301 module=model\.transport"):
        provider.generate_json("return JSON")

    assert len(attempts) == 2


def test_cache_write_failure_does_not_retry_or_discard_model_result() -> None:
    attempts: list[int] = []

    class FailingCache:
        def get(self, _key: str) -> None:
            return None

        def set(self, _key: str, _value: object) -> None:
            raise OSError("cache unavailable")

    def transport(_prompt: str, _config: ModelConfig) -> str:
        attempts.append(1)
        return '{"answer": "ok"}'

    provider = ModelProvider(
        ModelConfig(max_retries=5),
        transport=transport,
        cache=FailingCache(),
    )

    result = provider.generate_json("return JSON", response_model=ExampleOutput)

    assert isinstance(result, ExampleOutput)
    assert result.answer == "ok"
    assert len(attempts) == 1
    assert provider.last_cache_error == "cache write failed (error_type=OSError)"


def test_cache_key_separates_model_providers() -> None:
    cache = InMemoryCache()
    calls: list[str] = []

    def transport(prompt: str, config: ModelConfig) -> dict[str, str]:
        calls.append(config.provider_name)
        return {"answer": config.provider_name}

    first = ModelProvider(
        ModelConfig(provider_name="provider-a", model_name="same-model"),
        transport=transport,
        cache=cache,
    )
    second = ModelProvider(
        ModelConfig(provider_name="provider-b", model_name="same-model"),
        transport=transport,
        cache=cache,
    )

    assert first.generate_json("same prompt") == {"answer": "provider-a"}
    assert second.generate_json("same prompt") == {"answer": "provider-b"}
    assert calls == ["provider-a", "provider-b"]


def test_custom_cache_key_is_hashed_before_persistent_write(tmp_path: Path) -> None:
    cache_path = tmp_path / "model-cache.json"
    provider = ModelProvider(
        ModelConfig(max_retries=0),
        transport=lambda _prompt, _config: '{"answer": "ok"}',
        cache=JsonFileCache(cache_path),
    )
    sensitive_looking_key = "prompt fixture-only evidence text"

    provider.generate_json("return JSON", cache_key=sensitive_looking_key)

    cache_text = cache_path.read_text(encoding="utf-8")
    assert sensitive_looking_key not in cache_text
    assert len(json.loads(cache_text)) == 1


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
