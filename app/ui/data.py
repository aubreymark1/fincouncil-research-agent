"""Read-only data access layer for the D-006 Streamlit UI.

The UI only reads structured files (report.json, run_metadata.json,
metrics.json) and never modifies them.  This module is intentionally free of
Streamlit imports so it can be unit-tested in a plain Python environment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas import ResearchReport, RunMetadata

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "fixtures" / "evaluation" / "report_sample.json"
DEFAULT_METADATA_PATH: Path | None = None


def _read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"file does not exist: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"file is not valid JSON: {p} ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"file root must be an object: {p}")
    return payload


def load_report(path: str | Path) -> ResearchReport:
    """Load and validate a report.json."""
    return ResearchReport.model_validate(_read_json(path))


def load_run_metadata(path: str | Path) -> RunMetadata:
    """Load and validate a run_metadata.json."""
    return RunMetadata.model_validate(_read_json(path))


def load_metrics(path: str | Path) -> dict[str, Any]:
    """Load a metrics.json without requiring a fixed schema."""
    return _read_json(path)


def build_ui_model(
    report_path: str | Path,
    metadata_path: str | Path | None = None,
    metrics_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a read-only dictionary used by the Streamlit renderer."""
    report = load_report(report_path)
    model: dict[str, Any] = {
        "report": report.model_dump(mode="json"),
        "run_metadata": None,
        "metrics": None,
    }
    if metadata_path is not None:
        model["run_metadata"] = load_run_metadata(metadata_path).model_dump(mode="json")
    if metrics_path is not None:
        model["metrics"] = load_metrics(metrics_path)
    return model
