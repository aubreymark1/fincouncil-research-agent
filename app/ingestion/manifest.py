"""Manifest loading and validation for source documents.

B-001: read a source manifest (CSV or JSON), build :class:`SourceDocument`
objects, and return structured :class:`ValidationIssue` items for semantic
problems such as duplicate ``doc_id`` or a formal source without a publication
date.

The public function signatures follow ``docs/CONTRACTS.md`` exactly::

    load_manifest(path: str) -> list[SourceDocument]
    validate_manifest(documents: list[SourceDocument]) -> list[ValidationIssue]

Load-time problems (a record that cannot become a valid SourceDocument) raise
:class:`ManifestError` with a shared error code so the CLI can report the
module, file, and a suggested action. Validation-time problems (a document
that parses but is semantically invalid) are returned as ``ValidationIssue``
items and are never silently dropped.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import SourceDocument, ValidationIssue


#: Absolute project root, used to resolve manifest-relative ``local_path``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Fields required by :class:`SourceDocument`; must be present and non-empty.
_REQUIRED_FIELDS = (
    "doc_id",
    "title",
    "source_type",
    "publisher",
    "local_path",
    "retrieved_at",
    "trust_level",
    "review_status",
)

#: Review statuses allowed by the SourceDocument Literal.
_REVIEW_STATUSES = {
    "formal",
    "background",
    "pending_date",
    "red_team",
    "rejected",
}


class ManifestError(Exception):
    """Raised when a manifest cannot be read or a record cannot be parsed.

    ``code`` is one of the shared error codes from docs/CONTRACTS.md
    (E100/E101/E102).
    """

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} module=ingestion file={path}: {message}")


def _clean(value: Any) -> str:
    """Return a stripped string from a CSV cell or JSON value."""
    if value is None:
        return ""
    return str(value).strip()


def _parse_optional_date(value: str, *, field: str, path: str) -> date | None:
    if value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(
            "E102",
            path,
            f"{field}={value!r} is not a valid YYYY-MM-DD date",
        ) from exc


def _parse_required_datetime(value: str, *, field: str, path: str) -> datetime:
    if value == "":
        raise ManifestError("E101", path, f"missing required field {field}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(
            "E101",
            path,
            f"{field}={value!r} is not a valid ISO 8601 datetime",
        ) from exc


def _parse_trust_level(value: str, *, field: str, path: str) -> int:
    if value == "":
        raise ManifestError("E101", path, f"missing required field {field}")
    try:
        return int(value)
    except ValueError as exc:
        raise ManifestError(
            "E101",
            path,
            f"{field}={value!r} is not an integer",
        ) from exc


def _content_hash(local_path: str, path: str) -> str:
    """Compute a sha256 fingerprint of the source file's bytes.

    A missing file is a hard E100 error: the manifest points at source content
    that cannot be located, so registering the document would be unsafe.
    """
    resolved = Path(local_path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    if not resolved.is_file():
        raise ManifestError(
            "E100",
            path,
            f"local_path={local_path!r} does not resolve to an existing file",
        )
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _record_to_document(record: dict[str, Any], *, path: str) -> SourceDocument:
    for field in _REQUIRED_FIELDS:
        if _clean(record.get(field)) == "":
            raise ManifestError("E101", path, f"missing required field {field}")

    review_status = _clean(record["review_status"])
    if review_status not in _REVIEW_STATUSES:
        raise ManifestError(
            "E101",
            path,
            f"review_status={review_status!r} is not one of {sorted(_REVIEW_STATUSES)}",
        )

    published_at = _parse_optional_date(
        _clean(record.get("published_at")), field="published_at", path=path
    )
    event_date = _parse_optional_date(
        _clean(record.get("event_date")), field="event_date", path=path
    )
    retrieved_at = _parse_required_datetime(
        _clean(record.get("retrieved_at")), field="retrieved_at", path=path
    )
    trust_level = _parse_trust_level(
        _clean(record.get("trust_level")), field="trust_level", path=path
    )

    local_path = _clean(record["local_path"])
    content_hash = _content_hash(local_path, path=path)

    try:
        return SourceDocument(
            doc_id=_clean(record["doc_id"]),
            title=_clean(record["title"]),
            source_type=_clean(record["source_type"]),
            publisher=_clean(record["publisher"]),
            source_url=_clean(record.get("source_url")) or None,
            local_path=local_path,
            published_at=published_at,
            event_date=event_date,
            retrieved_at=retrieved_at,
            company_name=_clean(record.get("company_name")) or None,
            industry_id=_clean(record.get("industry_id")) or None,
            trust_level=trust_level,
            content_hash=content_hash,
            review_status=review_status,
        )
    except ValidationError as exc:
        errors = exc.errors()
        detail = errors[0].get("msg", str(exc)) if errors else str(exc)
        raise ManifestError(
            "E101",
            path,
            f"document fields failed validation: {detail}",
        ) from exc


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise ManifestError("E101", str(path), f"unable to parse CSV: {exc}") from exc


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError("E101", str(path), f"unable to parse JSON: {exc}") from exc

    if isinstance(payload, dict):
        payload = payload.get("documents")
    if not isinstance(payload, list):
        raise ManifestError(
            "E101",
            str(path),
            "JSON manifest must be a list of objects or contain a 'documents' list",
        )

    records: list[dict[str, Any]] = []
    for index, record in enumerate(payload, start=1):
        if not isinstance(record, dict):
            raise ManifestError(
                "E101",
                str(path),
                f"record {index} is not an object (got {type(record).__name__})",
            )
        records.append(record)
    return records


def load_manifest(path: str) -> list[SourceDocument]:
    """Read a manifest file and return the documents it declares."""
    manifest_path = Path(path)
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    if not manifest_path.is_file():
        raise ManifestError("E100", path, "manifest file does not exist")

    suffix = manifest_path.suffix.lower()
    if suffix == ".csv":
        records = _read_csv(manifest_path)
    elif suffix == ".json":
        records = _read_json(manifest_path)
    else:
        raise ManifestError(
            "E101",
            path,
            f"unsupported manifest format {suffix!r}; expected .csv or .json",
        )

    documents: list[SourceDocument] = []
    for index, record in enumerate(records, start=1):
        try:
            documents.append(_record_to_document(record, path=path))
        except ManifestError as exc:
            raise ManifestError(exc.code, path, f"record {index}: {exc.message}") from exc
    return documents


def _manifest_issue(
    *,
    document: SourceDocument,
    suffix: str,
    severity: str,
    issue_type: str,
    message: str,
    human_confirmation_required: bool,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=f"ISSUE-MANIFEST-{document.doc_id.removeprefix('DOC-')}-{suffix}",
        check_name="manifest_validation",
        severity=severity,
        issue_type=issue_type,
        message=message,
        claim_id=None,
        evidence_id=None,
        report_section="source_filter",
        rerun_required=False,
        human_confirmation_required=human_confirmation_required,
        status="open",
    )


def validate_manifest(documents: list[SourceDocument]) -> list[ValidationIssue]:
    """Return structured issues for semantically invalid documents.

    Checks covered by B-001:

    - duplicate ``doc_id`` (E101);
    - ``review_status == "formal"`` without a ``published_at`` (E102).
    """
    issues: list[ValidationIssue] = []
    seen: dict[str, int] = {}
    for document in documents:
        seen[document.doc_id] = seen.get(document.doc_id, 0) + 1

    reported_duplicates: set[str] = set()
    for document in documents:
        if seen[document.doc_id] > 1 and document.doc_id not in reported_duplicates:
            reported_duplicates.add(document.doc_id)
            issues.append(
                _manifest_issue(
                    document=document,
                    suffix="DUPLICATE-DOC-ID",
                    severity="error",
                    issue_type="duplicate_doc_id",
                    message=(
                        f"E101 {document.doc_id} appears {seen[document.doc_id]} times "
                        "in the manifest."
                    ),
                    human_confirmation_required=True,
                )
            )

        if document.review_status == "formal" and document.published_at is None:
            issues.append(
                _manifest_issue(
                    document=document,
                    suffix="FORMAL-MISSING-PUBLISHED-AT",
                    severity="error",
                    issue_type="missing_published_at",
                    message=(
                        f"E102 {document.doc_id} is review_status=formal but has no "
                        "published_at."
                    ),
                    human_confirmation_required=True,
                )
            )

    return issues
