"""Reproducible experiment runner for E0—E3 (D-003).

Each experiment writes a self-contained directory:

``outputs/experiments/{case_id}/{experiment_id}/``
    request.json
    report.json          (E0 imports a manual briefing; E1-E3 run the pipeline)
    run_metadata.json
    metrics.json
    error.txt            (present only on failure)

Failed experiments are never deleted: the directory stays on disk and the
aggregate results table records ``failed`` together with the error message.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from app.schemas import ResearchReport, ResearchRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEFINITIONS = PROJECT_ROOT / "evaluation" / "experiment_definitions.yaml"
DEFAULT_GOLD_DIR = PROJECT_ROOT / "fixtures" / "evaluation"

EXPECTED_EXPERIMENTS = ("E0", "E1", "E2", "E3")

# Callable that executes one experiment command and returns exit code + text.
Executor = Callable[[str], tuple[int, str]]


@dataclass(frozen=True)
class ExperimentDefinition:
    """A frozen entry from experiment_definitions.yaml."""

    experiment_id: str
    name: str
    description: str
    run_command: str | None


@dataclass(frozen=True)
class CaseDefinition:
    """One case (资料包 + cutoff + Gold) from experiment_definitions.yaml."""

    case_id: str
    request_path: Path
    gold_path: Path | None


def _require_str(raw: Any, where: str, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: {key} must be a non-empty string")
    return value.strip()


def _require_mapping(raw: Any, where: str, key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{where}: {key} must be an object")
    return value


def _parse_cases(raw: dict[str, Any], root: Path) -> list[CaseDefinition]:
    cases: list[CaseDefinition] = []
    for index, item in enumerate(raw.get("cases", [])):
        where = f"cases[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where}: must be an object")
        case_id = _require_str(item, where, "case_id")
        request_path = Path(_require_str(item, where, "request_path"))
        if not request_path.is_absolute():
            request_path = root / request_path
        raw_gold = item.get("gold_path")
        gold_path: Path | None = None
        if raw_gold is not None:
            if not isinstance(raw_gold, str) or not raw_gold.strip():
                raise ValueError(f"{where}: gold_path must be null or a non-empty string")
            gold_path = Path(raw_gold.strip())
            if not gold_path.is_absolute():
                gold_path = root / gold_path
        cases.append(
            CaseDefinition(
                case_id=case_id,
                request_path=request_path,
                gold_path=gold_path,
            )
        )
    if not cases:
        raise ValueError("experiment definitions must declare at least one case")
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("experiment definitions case_id values must be unique")
    return cases


def _parse_experiments(raw: dict[str, Any]) -> dict[str, ExperimentDefinition]:
    experiments: dict[str, ExperimentDefinition] = {}
    for experiment_id, item in raw.get("experiments", {}).items():
        where = f"experiments[{experiment_id}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where}: must be an object")
        run_command = item.get("run_command")
        if run_command is not None and (
            not isinstance(run_command, str) or not run_command.strip()
        ):
            raise ValueError(f"{where}: run_command must be null or a non-empty string")
        experiments[experiment_id] = ExperimentDefinition(
            experiment_id=experiment_id,
            name=_require_str(item, where, "name"),
            description=_require_str(item, where, "description"),
            run_command=run_command.strip() if run_command else None,
        )
    return experiments


def load_definitions(
    path: str | Path = DEFAULT_DEFINITIONS,
) -> tuple[list[CaseDefinition], dict[str, ExperimentDefinition], dict[str, Any]]:
    """Load and validate the frozen experiment definition file."""
    defs_path = Path(path)
    try:
        payload = yaml.safe_load(defs_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"experiment definitions file does not exist: {defs_path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(
            f"experiment definitions file is not valid YAML: {defs_path} ({exc})"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("experiment definitions root must be an object")

    root = defs_path.resolve().parent
    cases = _parse_cases(payload, root)
    experiments = _parse_experiments(payload)

    if not experiments:
        raise ValueError("experiment definitions must declare at least one experiment")
    for experiment_id in EXPECTED_EXPERIMENTS:
        if experiment_id not in experiments:
            raise ValueError(
                f"experiment definitions must freeze the {experiment_id} experiment"
            )
    missing = [
        experiment_id
        for experiment_id, definition in experiments.items()
        if definition.run_command is None and experiment_id != "E0"
    ]
    if missing:
        raise ValueError(
            f"E1-E3 experiments must define a run_command; missing: {missing}"
        )

    return cases, experiments, payload.get("output", {})


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_input_hash(request: ResearchRequest, manifest_path: Path | str) -> dict[str, str]:
    """Stable sha256 hashes of the request and its manifest file."""
    request_hash = _sha256(
        json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    )
    manifest = Path(manifest_path)
    if not manifest.is_absolute():
        manifest = PROJECT_ROOT / manifest
    return {
        "request": f"sha256:{request_hash}",
        "manifest": f"sha256:{_sha256(manifest.read_bytes().decode('utf-8'))}",
    }


def _resolve_request(request_path: Path) -> ResearchRequest:
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    return ResearchRequest.model_validate(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _default_executor(command: str) -> tuple[int, str]:
    result = subprocess.run(
        command,
        shell=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _default_python() -> str:
    """Interpreter substituted for ``{python}`` in frozen run commands."""
    return subprocess.list2cmdline([sys.executable])


_PLACEHOLDER_PATTERN = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
_KNOWN_PLACEHOLDERS = ("{python}", "{request_path}")


def _render_command(template: str, request_path: Path, experiment_id: str) -> str:
    """Substitute the frozen placeholders of a run_command template.

    ``{python}`` resolves to the current interpreter and ``{request_path}``
    to the temporary request file, both shell-quoted via
    :func:`subprocess.list2cmdline` so paths with spaces stay a single
    argument. Any leftover ``{word}`` placeholder is a typo in the frozen
    definitions and must fail loudly instead of leaking into the shell.
    """
    command = template.replace("{python}", _default_python()).replace(
        "{request_path}", subprocess.list2cmdline([str(request_path)])
    )
    unknown = sorted(set(_PLACEHOLDER_PATTERN.findall(command)))
    if unknown:
        raise ValueError(
            "evaluation/experiment_runner.py: unknown placeholder(s) "
            f"{unknown} in {experiment_id} run_command after substitution; "
            f"expected one of {list(_KNOWN_PLACEHOLDERS)}"
        )
    return command


def _run_experiment_definition(
    experiment_id: str,
    definition: ExperimentDefinition,
    request: ResearchRequest,
    *,
    executor: Executor = _default_executor,
) -> tuple[int, str]:
    """Execute an E1-E3 run_command, substituting the frozen placeholders."""
    if not definition.run_command:
        raise ValueError(f"{experiment_id} has no run_command and is not E0")
    request_path = _write_temp_request(request, experiment_id)
    command = _render_command(definition.run_command, request_path, experiment_id)
    try:
        code, output = executor(command)
    finally:
        # Cleanup is best-effort: the experiment result must never be lost
        # because a sandbox refused to delete the temporary request copy.
        try:
            request_path.unlink(missing_ok=True)
        except OSError:
            pass
    return code, output


def _write_temp_request(request: ResearchRequest, tag: str) -> Path:
    """Persist a request for one frozen command run.

    The file is used as the ``{request_path}`` substitution target; it is a
    short-lived copy and cleanup must never fail the experiment (sandboxes can
    reject file deletion, which is not an execution failure).
    """

    temp_dir = PROJECT_ROOT / "outputs" / "experiments" / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    path = temp_dir / f"{request.run_id}-{tag}.json"
    _write_json(path, request.model_dump(mode="json"))
    return path


def _collect_run_outputs(
    experiment_dir: Path,
    request: ResearchRequest,
    metadata: dict[str, Any],
    *,
    metrics: dict[str, Any],
    error: str | None,
    report: ResearchReport | None = None,
) -> None:
    """Persist every experiment artefact; failed runs keep report/metadata too."""
    experiment_dir.mkdir(parents=True, exist_ok=True)
    _write_json(experiment_dir / "request.json", request.model_dump(mode="json"))
    if report is not None:
        _write_json(experiment_dir / "report.json", report.model_dump(mode="json"))
    if metadata is not None:
        _write_json(experiment_dir / "run_metadata.json", metadata)
    if metrics is not None:
        _write_json(experiment_dir / "metrics.json", metrics)
    if error:
        (experiment_dir / "error.txt").write_text(error, encoding="utf-8")


def _read_report(path: Path) -> ResearchReport:
    return ResearchReport.model_validate_json(path.read_text(encoding="utf-8"))


def run_experiment(
    experiment_id: str,
    request: ResearchRequest,
    *,
    definitions: str | Path = DEFAULT_DEFINITIONS,
    gold_path: str | Path | None = None,
    executor: Executor = _default_executor,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Run one experiment and return the experiment result row.

    E0 raises when called directly; manual baselines must be imported with
    :func:`import_manual_baseline`, which keeps timings and the human text.
    E1-E3 invoke their frozen run_command and collect whatever the pipeline
    produced, preserving failures in the result row and error.txt.
    """
    if experiment_id == "E0":
        raise ValueError(
            "E0 is a manual baseline; call import_manual_baseline() instead"
        )
    _, experiments, _ = load_definitions(definitions)
    definition = experiments.get(experiment_id)
    if definition is None:
        raise ValueError(
            f"unknown experiment {experiment_id!r}; expected one of {sorted(experiments)}"
        )

    started_at = datetime.now(timezone.utc)
    case = case_id or "default"
    experiment_dir = (
        PROJECT_ROOT / "outputs" / "experiments" / case / experiment_id
    )
    input_hashes = compute_input_hash(request, request.source_manifest_path)

    result = {
        "experiment_id": experiment_id,
        "name": definition.name,
        "case_id": case,
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "status": "running",
        "input_hashes": input_hashes,
        "gold_path": str(gold_path) if gold_path else None,
        "metrics": None,
        "error": None,
    }

    try:
        code, output = _run_experiment_definition(
            experiment_id, definition, request, executor=executor
        )
        finished_at = datetime.now(timezone.utc)
        result["finished_at"] = finished_at.isoformat()

        report_path = _find_report(request)
        metadata_path = _find_metadata(request)
        report = _read_report(report_path)
        metadata = _read_metadata(metadata_path)

        metrics: dict[str, float] | None = None
        if gold_path:
            from evaluation.metrics import evaluate_report

            metrics = evaluate_report(report, str(gold_path))
        result["metrics"] = metrics

        if code != 0:
            result["status"] = "failed"
            result["error"] = output.strip() or f"exit code {code}"
        else:
            result["status"] = "success"

        _collect_run_outputs(
            experiment_dir,
            request,
            metadata,
            metrics={"status": result["status"], "metrics": metrics},
            error=result["error"],
            report=report,
        )
    except Exception as exc:  # noqa: BLE001 - failures must be recorded, not lost
        finished_at = datetime.now(timezone.utc)
        result["finished_at"] = finished_at.isoformat()
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        _collect_run_outputs(
            experiment_dir,
            request,
            None,
            metrics=None,
            error=result["error"],
        )

    return result


def _find_report(request: ResearchRequest) -> Path:
    output_dir = Path(request.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    return output_dir / "report.json"


def _find_metadata(request: ResearchRequest) -> Path:
    output_dir = Path(request.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    outputs_root = next(
        (parent for parent in (output_dir, *output_dir.parents) if parent.name.lower() == "outputs"),
        PROJECT_ROOT / "outputs",
    )
    return outputs_root / "logs" / request.run_id / "run_metadata.json"


def _read_metadata(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def import_manual_baseline(
    request: ResearchRequest,
    *,
    text: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    sources_used: list[str] | None = None,
    definitions: str | Path = DEFAULT_DEFINITIONS,
    case_id: str | None = None,
) -> dict[str, Any]:
    """Import an E0 manual briefing into a validated ResearchReport.

    The human text is preserved verbatim (it is never rewritten) and the
    resulting record carries the timing and source metadata recorded by the
    manual author.
    """
    _, experiments, _ = load_definitions(definitions)
    definition = experiments.get("E0")
    if definition is None:
        raise ValueError("E0 experiment is missing from experiment definitions")

    now = datetime.now(timezone.utc)
    report = ResearchReport(
        run_id=request.run_id,
        company_name=request.company_name,
        industry_id=request.industry_id,
        cutoff_date=request.cutoff_date,
        summary=[text],
        claims=[],
        risks=[],
        unresolved_items=[],
        evidence_index=[],
        validation_issues=[],
        generated_at=now,
        report_version="e0-manual-baseline",
    )

    case = case_id or "default"
    experiment_dir = PROJECT_ROOT / "outputs" / "experiments" / case / "E0"
    input_hashes = compute_input_hash(request, request.source_manifest_path)

    metadata: dict[str, Any] = {
        "experiment_id": "E0",
        "name": definition.name,
        "case_id": case,
        "started_at": started_at or now.isoformat(),
        "finished_at": finished_at or now.isoformat(),
        "status": "success",
        "model_provider": "manual",
        "model_name": "human-baseline",
        "input_hashes": input_hashes,
        "sources_used": sources_used or [],
        "errors": [],
    }
    _write_json(experiment_dir / "request.json", request.model_dump(mode="json"))
    _write_json(experiment_dir / "report.json", report.model_dump(mode="json"))
    _write_json(experiment_dir / "run_metadata.json", metadata)
    _write_json(experiment_dir / "metrics.json", {"status": "success", "metrics": None})

    return {
        "experiment_id": "E0",
        "name": definition.name,
        "case_id": case,
        "status": "success",
        "input_hashes": input_hashes,
        "started_at": metadata["started_at"],
        "finished_at": metadata["finished_at"],
        "metrics": None,
        "gold_path": None,
        "error": None,
        "report_path": str(experiment_dir / "report.json"),
    }


def run_case_experiments(
    case_id: str,
    request: ResearchRequest,
    *,
    experiments: tuple[str, ...] = EXPECTED_EXPERIMENTS,
    definitions: str | Path = DEFAULT_DEFINITIONS,
    executor: Executor = _default_executor,
    gold_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Run several experiments for one case and write the aggregate table."""
    cases, experiment_defs, output_cfg = load_definitions(definitions)
    case = next((item for item in cases if item.case_id == case_id), None)
    if case is None:
        raise ValueError(f"unknown case {case_id!r}; expected one of {[c.case_id for c in cases]}")

    effective_gold = gold_path if gold_path is not None else case.gold_path
    rows: list[dict[str, Any]] = []
    for experiment_id in experiments:
        if experiment_id not in experiment_defs:
            raise ValueError(f"unknown experiment {experiment_id!r}")
        if experiment_id == "E0":
            continue
        row = run_experiment(
            experiment_id,
            request,
            definitions=definitions,
            gold_path=effective_gold,
            executor=executor,
            case_id=case_id,
        )
        rows.append(row)

    _write_aggregate(case_id, rows, output_cfg)
    return rows


def _write_aggregate(
    case_id: str,
    rows: list[dict[str, Any]],
    output_cfg: dict[str, Any],
) -> None:
    """Write results.json (full rows) and results.csv (flattened metrics)."""
    root_cfg = output_cfg.get("root", "outputs/experiments") if isinstance(output_cfg, dict) else "outputs/experiments"
    root = Path(root_cfg)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    case_dir = root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_json(case_dir / "results.json", rows)

    headers = [
        "experiment_id",
        "name",
        "case_id",
        "status",
        "started_at",
        "finished_at",
        "input_hash_request",
        "input_hash_manifest",
        "key_factor_coverage_rate",
        "evidence_validity_rate",
        "citation_location_accuracy_rate",
        "numeric_error_rate",
        "cutoff_violation_count",
        "industry_metric_coverage_rate",
        "gold_path",
        "error",
    ]
    lines = [",".join(headers)]
    for row in rows:
        metrics = row.get("metrics") or {}
        values = [
            str(row.get("experiment_id", "")),
            str(row.get("name", "")),
            str(row.get("case_id", "")),
            str(row.get("status", "")),
            str(row.get("started_at", "")),
            str(row.get("finished_at", "")),
            str((row.get("input_hashes") or {}).get("request", "")),
            str((row.get("input_hashes") or {}).get("manifest", "")),
            str(metrics.get("key_factor_coverage_rate", "")),
            str(metrics.get("evidence_validity_rate", "")),
            str(metrics.get("citation_location_accuracy_rate", "")),
            str(metrics.get("numeric_error_rate", "")),
            str(metrics.get("cutoff_violation_count", "")),
            str(metrics.get("industry_metric_coverage_rate", "")),
            str(row.get("gold_path", "")),
            str(row.get("error", "") or ""),
        ]
        lines.append(",".join(_csv_escape(value) for value in values))
    (case_dir / "results.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _csv_escape(value: str) -> str:
    if "," in value or '"' in value or "\n" in value:
        return '"' + value.replace('"', '""') + '"'
    return value
