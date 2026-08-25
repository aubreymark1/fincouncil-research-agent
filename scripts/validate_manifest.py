"""Validate a source manifest and print structured issues.

Usage::

    python scripts/validate_manifest.py data/manifests/food_case.csv

Exit codes: 0 = passed, 1 = validation issues, 2 = unreadable/unparseable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion import ManifestError, load_manifest, validate_manifest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a source manifest.")
    parser.add_argument("manifest", type=str, help="Path to a manifest CSV or JSON file")
    args = parser.parse_args(argv)

    try:
        documents = load_manifest(args.manifest)
    except ManifestError as exc:
        print(
            f"{exc.code} module=ingestion file={args.manifest}: {exc.message} "
            "Fix the manifest and retry.",
            file=sys.stderr,
        )
        return 2

    issues = validate_manifest(documents)
    if issues:
        for issue in issues:
            print(
                f"[{issue.severity}] {issue.issue_type} {issue.issue_id}: {issue.message}",
                file=sys.stderr,
            )
        print(
            f"validation failed: {len(issues)} issue(s) across {len(documents)} document(s)",
            file=sys.stderr,
        )
        return 1

    print(f"validation passed: {len(documents)} document(s), 0 issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
