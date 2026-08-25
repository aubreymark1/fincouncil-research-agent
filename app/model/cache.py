"""Small JSON-compatible caches for model responses."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class CacheError(RuntimeError):
    """Raised when a cache cannot be read or written safely."""


class ModelCache(Protocol):
    """Minimal cache interface consumed by ModelProvider."""

    def get(self, key: str) -> Any | None:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


class InMemoryCache:
    """Deterministic cache for tests and short-lived processes."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._values.get(key)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value


class JsonFileCache:
    """A small persistent cache containing only JSON model responses."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CacheError("model cache could not be read") from exc
        if not isinstance(payload, dict):
            raise CacheError("model cache root must be a JSON object")
        return payload

    def get(self, key: str) -> Any | None:
        return self._read().get(key)

    def set(self, key: str, value: Any) -> None:
        payload = self._read()
        payload[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            raise CacheError("model cache could not be written") from exc


def make_cache_key(
    *,
    prompt: str,
    provider_name: str,
    model_name: str,
    base_url: str | None,
    temperature: float,
    response_model_name: str | None = None,
) -> str:
    """Create a stable key without storing the prompt or credentials."""

    payload: Mapping[str, Any] = {
        "prompt": prompt,
        "provider_name": provider_name,
        "model_name": model_name,
        "base_url": base_url,
        "temperature": temperature,
        "response_model": response_model_name,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def hash_cache_key(value: str) -> str:
    """Hash caller-provided keys before they reach a persistent cache."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
