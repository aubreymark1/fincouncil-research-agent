"""Command-line entry point for the minimum research case."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import run_research  # noqa: E402
from app.schemas import ResearchRequest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the minimum FinCouncil research case.")
    parser.add_argument("--request", required=True, type=Path, help="Path to a ResearchRequest JSON file")
    args = parser.parse_args(argv)

    try:
        request_payload = json.loads(args.request.read_text(encoding="utf-8"))
        request = ResearchRequest.model_validate(request_payload)
        report = run_research(request)
    except Exception as exc:
        print(
            f"E500 module=cli file={args.request}: {exc}. "
            "Check the request, fixture paths, and output directory.",
            file=sys.stderr,
        )
        return 2

    report_path = Path(request.output_dir) / "report.json"
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path
    outputs_root = next(
        (parent for parent in (report_path.parent, *report_path.parent.parents) if parent.name.lower() == "outputs"),
        PROJECT_ROOT / "outputs",
    )
    metadata_path = outputs_root / "logs" / request.run_id / "run_metadata.json"
    print(
        json.dumps(
            {
                "run_id": report.run_id,
                "report_path": str(report_path.resolve()),
                "metadata_path": str(metadata_path.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
