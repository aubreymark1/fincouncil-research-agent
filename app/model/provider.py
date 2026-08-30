"""SDK-neutral model provider with structured JSON validation and bounded retries.

Environment variables:

``FINCOUNCIL_MODEL_PROVIDER``
``FINCOUNCIL_MODEL_NAME``
``FINCOUNCIL_MODEL_API_KEY``
``FINCOUNCIL_MODEL_BASE_URL``
``FINCOUNCIL_MODEL_TEMPERATURE``
``FINCOUNCIL_MODEL_MAX_RETRIES``
``FINCOUNCIL_MODEL_TIMEOUT_SECONDS``

The provider accepts a transport callable instead of importing a vendor SDK.
That keeps agents independent from a concrete model client and lets tests use
deterministic mocks.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import sleep
from typing import Any

from pydantic import BaseModel, ValidationError

from .cache import InMemoryCache, JsonFileCache, ModelCache, hash_cache_key, make_cache_key
from .tool_types import ToolDefinition, ToolTurn


MAX_RETRIES = 5
DEFAULT_TEMPERATURE = 0.0

JsonTransport = Callable[[str, "ModelConfig"], Any]
ToolTransport = Callable[[list[dict[str, Any]], list[ToolDefinition], "ModelConfig"], Any]


class ModelProviderError(RuntimeError):
    """A safe, coded error that does not expose prompt or credential contents."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        prefix = message.split(" ", 1)[0]
        self.code = prefix if (len(prefix) == 4 and prefix[0] == "E" and prefix[1:].isdigit()) else None


def _parse_float(env: Mapping[str, str], name: str, default: float) -> float:
    value = env.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _parse_int(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class ModelConfig:
    """Runtime model settings; the API key is excluded from repr output."""

    provider_name: str = "mock"
    model_name: str = "fixture"
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    temperature: float = DEFAULT_TEMPERATURE
    max_retries: int = 2
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.provider_name:
            raise ValueError("provider_name must not be empty")
        if not self.model_name:
            raise ValueError("model_name must not be empty")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.max_retries > MAX_RETRIES:
            object.__setattr__(self, "max_retries", MAX_RETRIES)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ModelConfig":
        values = os.environ if env is None else env
        api_key = values.get("FINCOUNCIL_MODEL_API_KEY") or None
        base_url = values.get("FINCOUNCIL_MODEL_BASE_URL") or None
        return cls(
            provider_name=values.get("FINCOUNCIL_MODEL_PROVIDER", "mock"),
            model_name=values.get("FINCOUNCIL_MODEL_NAME", "fixture"),
            api_key=api_key,
            base_url=base_url,
            temperature=_parse_float(
                values,
                "FINCOUNCIL_MODEL_TEMPERATURE",
                DEFAULT_TEMPERATURE,
            ),
            max_retries=_parse_int(values, "FINCOUNCIL_MODEL_MAX_RETRIES", 2),
            timeout_seconds=_parse_float(
                values,
                "FINCOUNCIL_MODEL_TIMEOUT_SECONDS",
                30.0,
            ),
        )


def _strip_json_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    # Some otherwise valid model responses prepend a short explanation or
    # append a closing sentence. Extract the outer JSON object while leaving
    # schema validation unchanged.
    start = value.find("{")
    end = value.rfind("}")
    if start > 0 and end > start:
        value = value[start : end + 1]
    return value


def _as_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, BaseModel):
        payload = raw.model_dump(mode="json")
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    elif isinstance(raw, str):
        try:
            payload = json.loads(_strip_json_fence(raw))
        except json.JSONDecodeError as exc:
            raise ValueError("transport returned invalid JSON") from exc
    else:
        raise ValueError("transport must return a JSON object or JSON string")
    if not isinstance(payload, dict):
        raise ValueError("structured model output must be a JSON object")
    return payload


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class ModelProvider:
    """SDK-neutral provider for validated structured model responses."""

    def __init__(
        self,
        config: ModelConfig | None = None,
        *,
        transport: JsonTransport | None = None,
        tool_transport: ToolTransport | None = None,
        cache: ModelCache | None = None,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self.config = config or ModelConfig()
        self._transport = transport
        self._tool_transport = tool_transport
        self._cache = cache
        self._sleep = sleep_fn
        self.last_cache_error: str | None = None

    @property
    def cache(self) -> ModelCache | None:
        """Return the configured model cache, if any."""
        return self._cache

    @property
    def has_cache(self) -> bool:
        """Return whether a model cache is configured."""
        return self.cache is not None

    @property
    def has_tool_transport(self) -> bool:
        return self._tool_transport is not None

    @property
    def cache_version(self) -> str:
        """Return the audit version for the configured cache type."""
        if self.cache is None:
            return "none"
        if isinstance(self.cache, JsonFileCache):
            return "v1-json"
        if isinstance(self.cache, InMemoryCache):
            return "v1-memory"
        return f"v1-{type(self.cache).__name__.lower()}"

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        transport: JsonTransport | None = None,
        tool_transport: ToolTransport | None = None,
        cache: ModelCache | None = None,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> "ModelProvider":
        return cls(
            config=ModelConfig.from_env(env),
            transport=transport,
            tool_transport=tool_transport,
            cache=cache,
            sleep_fn=sleep_fn,
        )

    def generate_json(
        self,
        prompt: str,
        *,
        response_model: type[BaseModel] | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any] | BaseModel:
        """Return a JSON object, optionally validated by a Pydantic model."""

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if self._transport is None:
            raise ModelProviderError("E300 module=model: no transport configured")

        response_model_name = None
        if response_model is not None:
            response_model_name = f"{response_model.__module__}.{response_model.__qualname__}"
        key = (
            hash_cache_key(cache_key)
            if cache_key is not None
            else make_cache_key(
                prompt=prompt,
                provider_name=self.config.provider_name,
                model_name=self.config.model_name,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                response_model_name=response_model_name,
            )
        )

        self.last_cache_error = None
        if self._cache is not None:
            try:
                cached = self._cache.get(key)
            except Exception as exc:
                self.last_cache_error = f"cache read failed (error_type={type(exc).__name__})"
                cached = None
            if cached is not None:
                try:
                    return self._validate(cached, response_model)
                except (TypeError, ValueError, ValidationError):
                    pass

        attempts = self.config.max_retries + 1
        last_transport_error_type = "UnknownError"
        for attempt in range(attempts):
            try:
                raw = self._transport(prompt, self.config)
            except Exception as exc:
                last_transport_error_type = type(exc).__name__
                if attempt == attempts - 1:
                    if isinstance(exc, ModelProviderError) and exc.code == "E301":
                        raise
                    raise ModelProviderError(
                        f"E300 module=model: transport failed after {attempts} attempts "
                        f"(error_type={last_transport_error_type})"
                    ) from None
                self._sleep(0)
                continue

            try:
                payload = _as_json_object(raw)
                result = self._validate(payload, response_model)
            except (TypeError, ValueError, ValidationError) as exc:
                if attempt == attempts - 1:
                    detail = type(exc).__name__
                    if isinstance(exc, ValidationError):
                        fields = sorted({".".join(str(part) for part in error.get("loc", ())) for error in exc.errors()})
                        detail = f"{detail}; fields={','.join(fields[:8])}"
                    raise ModelProviderError(
                        f"E301 module=model: output could not be parsed after {attempts} attempts "
                        f"(error_type={detail})"
                    ) from None
                self._sleep(0)
                continue

            if self._cache is not None:
                try:
                    self._cache.set(key, _to_jsonable(result))
                except Exception as exc:
                    self.last_cache_error = f"cache write failed (error_type={type(exc).__name__})"
            return result

        raise ModelProviderError("E300 module=model: transport failed")

    def generate(
        self,
        prompt: str,
        *,
        response_model: type[BaseModel] | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any] | BaseModel:
        """Compatibility alias for agents that call the provider generically."""

        return self.generate_json(
            prompt,
            response_model=response_model,
            cache_key=cache_key,
        )

    def run_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
        dispatcher: Callable[[str, dict[str, Any]], Any],
        *,
        response_model: type[BaseModel] | None = None,
        max_tool_calls: int = 6,
    ) -> dict[str, Any] | BaseModel:
        """Run a bounded tool-calling conversation and validate its final JSON."""

        if self._tool_transport is None:
            raise ModelProviderError("E300 module=model: tool transport is not configured")
        if max_tool_calls < 0:
            raise ValueError("max_tool_calls must not be negative")
        allowed_tools = {tool.name for tool in tools}
        conversation = list(messages)
        tool_calls_used = 0
        while True:
            raw_turn = self._tool_transport(conversation, tools, self.config)
            turn = raw_turn if isinstance(raw_turn, ToolTurn) else ToolTurn.model_validate(raw_turn)
            if turn.tool_calls:
                if tool_calls_used + len(turn.tool_calls) > max_tool_calls:
                    raise ModelProviderError("E300 module=model: tool call limit exceeded")
                conversation.append({
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                        }
                        for call in turn.tool_calls
                    ],
                })
                for call in turn.tool_calls:
                    if call.name not in allowed_tools:
                        raise ModelProviderError(f"E300 module=model: unknown tool {call.name!r}")
                    try:
                        result = dispatcher(call.name, call.arguments)
                    except Exception as exc:  # noqa: BLE001 - hide tool internals from model errors
                        raise ModelProviderError(
                            f"E300 module=model: tool {call.name!r} failed ({type(exc).__name__})"
                        ) from None
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str)[:32768],
                    })
                tool_calls_used += len(turn.tool_calls)
                continue
            if not turn.content:
                raise ModelProviderError("E301 module=model: tool turn has no final content")
            try:
                payload = _as_json_object(turn.content)
                return self._validate(payload, response_model)
            except (TypeError, ValueError, ValidationError) as exc:
                raise ModelProviderError(
                    f"E301 module=model: final tool response could not be parsed ({type(exc).__name__})"
                ) from None

    @staticmethod
    def _validate(
        payload: dict[str, Any],
        response_model: type[BaseModel] | None,
    ) -> dict[str, Any] | BaseModel:
        if response_model is None:
            return payload
        return response_model.model_validate(payload)
