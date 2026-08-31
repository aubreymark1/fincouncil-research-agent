"""Real HTTP transport for OpenAI-compatible chat completions.

This module deliberately uses only the Python standard library so agents never
depend on a vendor SDK. The returned callable satisfies
``app.model.provider.JsonTransport``: it takes a prompt and ``ModelConfig`` and
returns the assistant message content (usually a JSON string) for
``ModelProvider`` to parse and validate.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .provider import ModelConfig, ModelProviderError
from .tool_types import ToolCall, ToolDefinition, ToolTurn


DEFAULT_BASE_URL = "https://api.openai.com/v1"

JsonTransport = Callable[[str, ModelConfig], Any]


def _is_deepseek(config: ModelConfig) -> bool:
    return "deepseek" in config.provider_name.casefold() or "deepseek.com" in (config.base_url or "").casefold()


def openai_compatible_transport(prompt: str, config: ModelConfig) -> str:
    """Call an OpenAI-compatible ``/chat/completions`` endpoint.

    The API key is read from ``config.api_key`` (populated from environment
    variables by ``ModelConfig.from_env``) and is never logged or persisted.
    """

    if not config.api_key:
        raise ModelProviderError(
            "E300 module=model.transport: FINCOUNCIL_MODEL_API_KEY is not set"
        )

    base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": config.model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
    }
    if _is_deepseek(config):
        payload["thinking"] = {"type": "disabled"}
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
    }
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        message = (
            f"E300 module=model.transport: HTTP {exc.code} from "
            f"{config.provider_name}"
        )
        if detail:
            message = f"{message}: {detail}"
        raise ModelProviderError(message) from None
    except Exception as exc:
        raise ModelProviderError(
            f"E300 module=model.transport: request failed "
            f"(error_type={type(exc).__name__})"
        ) from None

    try:
        decoded = json.loads(raw)
        choice = decoded["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            reasoning = message.get("reasoning_content")
            reasoning_chars = len(reasoning) if isinstance(reasoning, str) else 0
            completion_tokens = (decoded.get("usage") or {}).get("completion_tokens", "unknown")
            raise ModelProviderError(
                "E301 module=model.transport: empty chat content "
                f"(finish_reason={choice.get('finish_reason', 'unknown')}; "
                f"reasoning_chars={reasoning_chars}; completion_tokens={completion_tokens})"
            )
        return content
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ModelProviderError(
            "E301 module=model.transport: response missing chat content"
        ) from None


def create_openai_compatible_transport() -> JsonTransport:
    """Return the OpenAI-compatible transport callable."""

    return openai_compatible_transport


def openai_compatible_tool_transport(
    messages: list[dict[str, Any]],
    tools: list[ToolDefinition],
    config: ModelConfig,
) -> ToolTurn:
    """Call a tool-capable OpenAI-compatible chat endpoint."""

    if not config.api_key:
        raise ModelProviderError(
            "E300 module=model.transport: FINCOUNCIL_MODEL_API_KEY is not set"
        )
    base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
    payload = {
        "model": config.model_name,
        "messages": messages,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ],
        "tool_choice": "auto",
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if _is_deepseek(config):
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
        message = decoded["choices"][0]["message"]
        raw_calls = message.get("tool_calls") or []
        calls: list[ToolCall] = []
        for raw_call in raw_calls:
            function = raw_call["function"]
            raw_arguments = function.get("arguments") or "{}"
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            calls.append(ToolCall(id=raw_call["id"], name=function["name"], arguments=arguments))
        return ToolTurn(content=message.get("content"), tool_calls=calls)
    except urllib.error.HTTPError as exc:
        raise ModelProviderError(
            f"E300 module=model.transport: HTTP {exc.code} from {config.provider_name}"
        ) from None
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ModelProviderError(
            f"E301 module=model.transport: invalid tool response ({type(exc).__name__})"
        ) from None


def create_openai_compatible_tool_transport() -> Callable[[list[dict[str, Any]], list[ToolDefinition], ModelConfig], ToolTurn]:
    return openai_compatible_tool_transport
