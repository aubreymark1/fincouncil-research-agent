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


DEFAULT_BASE_URL = "https://api.openai.com/v1"

JsonTransport = Callable[[str, ModelConfig], Any]


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
    }
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
        return decoded["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ModelProviderError(
            "E301 module=model.transport: response missing chat content"
        ) from None


def create_openai_compatible_transport() -> JsonTransport:
    """Return the OpenAI-compatible transport callable."""

    return openai_compatible_transport
