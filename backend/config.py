"""Runtime settings for the anonymous workbench backend.

Only non-secret values are read here. API keys are read directly by
``app.model`` from environment variables and are never returned to clients.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_ENV_KEYS = (
    "FINCOUNCIL_MODEL_PROVIDER",
    "FINCOUNCIL_MODEL_NAME",
    "FINCOUNCIL_MODEL_BASE_URL",
    "FINCOUNCIL_MODEL_API_KEY",
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    """Backend configuration derived from environment variables."""

    project_root: Path = PROJECT_ROOT
    outputs_dir: Path = PROJECT_ROOT / "outputs"
    db_path: Path = PROJECT_ROOT / "outputs" / "workbench.db"
    static_dir: Path | None = PROJECT_ROOT / "frontend" / "dist"
    llm_available_override: bool | None = None
    enable_llm_demo: bool = False
    max_runs_per_ip_per_minute: int = 10
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = PROJECT_ROOT
        outputs_dir = _resolve_path(project_root, os.getenv("FINCOUNCIL_OUTPUTS_DIR"))
        db_raw = os.getenv("FINCOUNCIL_DB_PATH")
        db_path = (
            _resolve_path(project_root, db_raw)
            if db_raw
            else outputs_dir / "workbench.db"
        )

        static_raw = os.getenv("WORKBENCH_STATIC_DIR", "").strip()
        static_dir = _resolve_path(project_root, static_raw) if static_raw else project_root / "frontend" / "dist"

        cors_raw = os.getenv("FINCOUNCIL_CORS_ORIGINS", "").strip()
        cors_origins = tuple(
            item.strip()
            for item in cors_raw.split(",")
            if item.strip()
        ) or ("http://localhost:5173", "http://127.0.0.1:5173")

        return cls(
            project_root=project_root,
            outputs_dir=outputs_dir,
            db_path=db_path,
            static_dir=static_dir,
            enable_llm_demo=_env_bool("FINCOUNCIL_ENABLE_LLM_DEMO"),
            max_runs_per_ip_per_minute=int(
                os.getenv("FINCOUNCIL_MAX_RUNS_PER_IP_PER_MINUTE", "10")
            ),
            cors_origins=cors_origins,
        )

    def llm_available(self) -> bool:
        """Return True only when the demo switch and all model env vars exist."""
        if self.llm_available_override is not None:
            return self.llm_available_override
        if not self.enable_llm_demo:
            return False
        return all(bool(os.getenv(key, "").strip()) for key in MODEL_ENV_KEYS)


def _resolve_path(project_root: Path, raw: str | None) -> Path:
    if not raw:
        return project_root / "outputs"
    path = Path(raw)
    return path if path.is_absolute() else project_root / path
