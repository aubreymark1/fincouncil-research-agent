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
from evaluation.charts import METRIC_KEYS, load_results

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


def _read_json_with_text(path: str | Path) -> tuple[dict[str, Any], str]:
    """Read one JSON object and retain its original text for read-only export."""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"file does not exist: {p}")
    raw = p.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"file is not valid JSON: {p} ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"file root must be an object: {p}")
    return payload, raw


def load_report(path: str | Path) -> ResearchReport:
    """Load and validate a report.json."""
    return ResearchReport.model_validate(_read_json(path))


def load_report_markdown(path: str | Path) -> str:
    """Load the report Markdown without interpreting or rewriting its text."""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"file does not exist: {p}")
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"file is not valid UTF-8 text: {p}") from exc


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
    *,
    report_markdown_path: str | Path | None = None,
    results_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a strict read-only dictionary used by the Streamlit renderer.

    The original report-loading behavior is kept: a missing or invalid
    ``report.json`` raises.  Optional artifacts are loaded when supplied (or
    inferable) and are represented in the returned file-status map.
    """
    return _build_ui_model(
        report_path,
        metadata_path,
        metrics_path,
        report_markdown_path=report_markdown_path,
        results_path=results_path,
        allow_missing_report=False,
    )


def load_ui_model(
    report_path: str | Path,
    metadata_path: str | Path | None = None,
    metrics_path: str | Path | None = None,
    *,
    report_markdown_path: str | Path | None = None,
    results_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a tolerant UI model so failed runs remain inspectable.

    A failed pipeline may have metadata and an error log but no report.  The
    page can still show that run state instead of replacing the useful error
    with a traceback from the missing report file.
    """
    return _build_ui_model(
        report_path,
        metadata_path,
        metrics_path,
        report_markdown_path=report_markdown_path,
        results_path=results_path,
        allow_missing_report=True,
    )


def report_export_payloads(model: dict[str, Any]) -> dict[str, str]:
    """Return source artifact text for download buttons without writing files."""
    exports: dict[str, str] = {}
    if model.get("report_json") is not None:
        exports["report.json"] = str(model["report_json"])
    if model.get("report_markdown") is not None:
        exports["report.md"] = str(model["report_markdown"])
    return exports


def _build_ui_model(
    report_path: str | Path,
    metadata_path: str | Path | None,
    metrics_path: str | Path | None,
    *,
    report_markdown_path: str | Path | None,
    results_path: str | Path | None,
    allow_missing_report: bool,
) -> dict[str, Any]:
    report_file = Path(report_path)
    markdown_file = Path(report_markdown_path) if report_markdown_path else report_file.with_name("report.md")
    metadata_file = Path(metadata_path) if metadata_path else _infer_metadata_path(report_file)
    metrics_file = Path(metrics_path) if metrics_path else _infer_metrics_path(report_file)
    results_file = Path(results_path) if results_path else _infer_results_path(report_file)

    model: dict[str, Any] = {
        "report": None,
        "report_json": None,
        "report_markdown": None,
        "run_metadata": None,
        "metrics": None,
        "results": None,
        "experiment_rows": [],
        "file_status": {},
        "missing_files": [],
        "errors": [],
    }

    try:
        payload, raw = _read_json_with_text(report_file)
        report = ResearchReport.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - UI records artifact failures
        _record_artifact_failure(model, "report.json", report_file, exc)
        if not allow_missing_report:
            raise
    else:
        model["report"] = report.model_dump(mode="json")
        model["report_json"] = raw
        _record_loaded(model, "report.json", report_file)

    if markdown_file is not None:
        try:
            model["report_markdown"] = load_report_markdown(markdown_file)
        except Exception as exc:  # noqa: BLE001 - UI records optional failures
            _record_artifact_failure(model, "report.md", markdown_file, exc)
        else:
            _record_loaded(model, "report.md", markdown_file)

    if metadata_file is not None:
        try:
            model["run_metadata"] = load_run_metadata(metadata_file).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - UI records optional failures
            _record_artifact_failure(model, "run_metadata.json", metadata_file, exc)
        else:
            _record_loaded(model, "run_metadata.json", metadata_file)

    if metrics_file is not None:
        try:
            model["metrics"] = load_metrics(metrics_file)
        except Exception as exc:  # noqa: BLE001 - UI records optional failures
            _record_artifact_failure(model, "metrics.json", metrics_file, exc)
        else:
            _record_loaded(model, "metrics.json", metrics_file)

    if results_file is not None:
        try:
            model["results"] = [
                _normalize_result_row(row) for row in load_results(results_file)
            ]
            model["experiment_rows"] = list(model["results"])
        except Exception as exc:  # noqa: BLE001 - UI records optional failures
            _record_artifact_failure(model, "results", results_file, exc)
        else:
            _record_loaded(model, "results", results_file)

    if isinstance(model["run_metadata"], dict):
        model["run_status"] = model["run_metadata"].get("status")
        model["runtime_errors"] = list(model["run_metadata"].get("errors") or [])
    else:
        model["run_status"] = None
        model["runtime_errors"] = []
    return model


def _infer_metadata_path(report_path: Path) -> Path | None:
    run_id = report_path.parent.name
    if report_path.name == "report.json" and report_path.parent.parent.name == "reports":
        outputs_root = report_path.parent.parent.parent
        return outputs_root / "logs" / run_id / "run_metadata.json"
    return None


def _infer_metrics_path(report_path: Path) -> Path | None:
    candidate = report_path.parent / "metrics.json"
    return candidate if candidate.exists() else None


def _infer_results_path(report_path: Path) -> Path | None:
    if (
        report_path.name != "report.json"
        or report_path.parent.parent.parent.name != "experiments"
    ):
        return None
    candidate = report_path.parent.parent / "results.json"
    return candidate if candidate.exists() else None


def _record_loaded(model: dict[str, Any], name: str, path: Path) -> None:
    model["file_status"][name] = {"status": "loaded", "path": str(path)}


def _record_artifact_failure(
    model: dict[str, Any], name: str, path: Path, exc: Exception
) -> None:
    status = "missing" if not path.exists() else "invalid"
    message = f"{name}：{exc}"
    model["file_status"][name] = {
        "status": status,
        "path": str(path),
        "message": message,
    }
    model["errors"].append(message)
    if status == "missing":
        model["missing_files"].append(name)


def _normalize_result_row(row: dict[str, Any]) -> dict[str, Any]:
    """Expose flat CSV metric columns as a read-only nested view."""
    normalized = dict(row)
    if isinstance(row.get("metrics"), dict):
        return normalized
    metrics = {
        key: row[key]
        for key in METRIC_KEYS
        if key in row and row[key] is not None and row[key] != ""
    }
    normalized["metrics"] = metrics or None
    return normalized
