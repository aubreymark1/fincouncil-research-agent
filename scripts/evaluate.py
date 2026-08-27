"""Command-line entry point for reproducible E0-E3 experiments (D-003).

Reads the frozen ``evaluation/experiment_definitions.yaml``, loads the request
for the selected case, and either imports an E0 manual baseline or runs the
frozen E1-E3 command.  Experiment artefacts are written under
``outputs/experiments/{case_id}/{experiment_id}/`` and the aggregate
``results.json`` / ``results.csv`` are regenerated for the case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas import ResearchRequest  # noqa: E402
from evaluation.experiment_runner import (  # noqa: E402
    EXPECTED_EXPERIMENTS,
    load_definitions,
    run_case_experiments,
    run_experiment,
    import_manual_baseline,
)


def _load_request(request_path: Path) -> ResearchRequest:
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    return ResearchRequest.model_validate(payload)


def _resolve_case(definitions_path: Path, case_id: str) -> Path:
    cases, _, _ = load_definitions(definitions_path)
    match = next((case for case in cases if case.case_id == case_id), None)
    if match is None:
        available = ", ".join(case.case_id for case in cases)
        raise ValueError(
            f"unknown case {case_id!r}; expected one of: {available}"
        )
    return match.request_path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or import one D-003 experiment case.",
    )
    parser.add_argument(
        "--definitions",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "experiment_definitions.yaml",
        help="Path to the frozen experiment definitions (default: %(default)s)",
    )
    parser.add_argument(
        "--case",
        required=True,
        help="case_id from the experiment definitions, e.g. food_main",
    )
    parser.add_argument(
        "--experiment",
        choices=EXPECTED_EXPERIMENTS,
        help="experiment to run (E1, E2, E3) or import (E0)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="run all non-manual experiments (E1, E2, E3) for the case",
    )
    parser.add_argument(
        "--import-manual",
        action="store_true",
        help="import an E0 manual baseline instead of running a command",
    )
    parser.add_argument(
        "--text",
        type=str,
        help="E0 manual briefing text (verbatim, never rewritten)",
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        help="path to a file containing the E0 manual briefing text",
    )
    parser.add_argument(
        "--started-at",
        type=str,
        help="E0 manual start timestamp (ISO 8601)",
    )
    parser.add_argument(
        "--finished-at",
        type=str,
        help="E0 manual finish timestamp (ISO 8601)",
    )
    parser.add_argument(
        "--sources-used",
        nargs="*",
        help="source identifiers used by the manual author for E0",
    )
    return parser.parse_args(argv)


def _manual_text(args: argparse.Namespace) -> str:
    if args.text and args.text_file:
        raise ValueError("use either --text or --text-file, not both")
    if args.text_file is not None:
        return args.text_file.read_text(encoding="utf-8")
    if args.text is None:
        raise ValueError("E0 import requires --text or --text-file")
    return args.text


def _run(args: argparse.Namespace) -> int:
    definitions_path = Path(args.definitions)
    if not definitions_path.is_absolute():
        definitions_path = PROJECT_ROOT / definitions_path
    request_path = _resolve_case(definitions_path, args.case)

    if args.import_manual:
        if args.experiment is not None and args.experiment != "E0":
            raise ValueError("--import-manual only applies to E0")
        request = _load_request(request_path)
        row = import_manual_baseline(
            request,
            text=_manual_text(args),
            started_at=args.started_at,
            finished_at=args.finished_at,
            sources_used=args.sources_used,
            definitions=definitions_path,
            case_id=args.case,
        )
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return 0

    if args.experiment is None and not args.all:
        raise ValueError("choose --experiment E1|E2|E3 or --all")

    request = _load_request(request_path)
    cases, _, output_cfg = load_definitions(definitions_path)
    case = next((case for case in cases if case.case_id == args.case), None)
    gold_path = case.gold_path if case is not None else None

    if args.all:
        rows = run_case_experiments(
            args.case,
            request,
            definitions=definitions_path,
            gold_path=gold_path,
        )
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    row = run_experiment(
        args.experiment,
        request,
        definitions=definitions_path,
        gold_path=gold_path,
        case_id=args.case,
    )
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0 if row.get("status") == "success" else 1


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:  # noqa: BLE001 - CLI surfaces all user-facing failures
        print(f"E500 module=cli file={args.case}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
