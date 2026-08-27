"""Small JSON-compatible caches for model responses."""

from __future__ import annotations

import hashlib
import json
import os
import time
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
    """A small persistent cache containing only JSON model responses.

    Writes use a same-directory temporary file, ``fsync``, and ``os.replace``
    so a crash cannot leave the main cache file partially written. A lock file
    serializes writers across processes; stale locks are broken after a timeout.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def _acquire_lock(self, timeout: float = 5.0) -> Path:
        lock_path = self._lock_path()
        deadline = time.time() + timeout
        stale_after = 30.0
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > stale_after:
                    try:
                        lock_path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.time() >= deadline:
                    raise CacheError("model cache lock timeout")
                time.sleep(0.05)
                continue
            except OSError as exc:
                raise CacheError("model cache lock could not be acquired") from exc
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
            finally:
                os.close(fd)
            return lock_path

    @staticmethod
    def _release_lock(lock_path: Path) -> None:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

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

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self.path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            raise CacheError("model cache could not be written") from exc

    def set(self, key: str, value: Any) -> None:
        lock_path = self._acquire_lock()
        try:
            try:
                payload = self._read()
            except CacheError:
                payload = {}
            payload[key] = value
            self._write_payload(payload)
        finally:
            self._release_lock(lock_path)


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
