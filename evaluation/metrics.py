"""Deterministic report metrics backed by a reviewed Gold Standard file.

The evaluator deliberately performs no model calls and no fuzzy semantic
matching.  A Gold item is matched to a report claim by ``industry_metric_id``
and an exact (case-insensitive) ``expected_text`` substring.  This keeps test
and experiment runs reproducible and makes the human-reviewed Gold file the
source of truth.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.schemas import Claim, Evidence, ResearchReport


_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class _GoldSource:
    doc_id: str
    page: int | None
    publisher: str | None
    content_hash: str | None


@dataclass(frozen=True)
class _GoldItem:
    item_id: str
    item_type: str
    expected_text: str
    expected_value: Decimal | None
    unit: str | None
    required: bool
    sources: tuple[_GoldSource, ...]
    industry_metric_id: str | None
    evidence_requirement: str


def _rate(numerator: int, denominator: int) -> float:
    """Return a stable 0..1 rate; an empty population is defined as 0.0."""

    return numerator / denominator if denominator else 0.0


def _required_string(raw: dict[str, Any], field: str, item_id: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Gold item {item_id}: {field} must be a non-empty string")
    return value.strip()


def _optional_string(raw: dict[str, Any], field: str, item_id: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Gold item {item_id}: {field} must be null or a non-empty string")
    return value.strip()


def _parse_expected_value(raw: dict[str, Any], item_id: str) -> Decimal | None:
    value = raw.get("expected_value")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"Gold item {item_id}: expected_value must be numeric or null")
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(
            f"Gold item {item_id}: expected_value must be numeric or null"
        ) from exc
    if not parsed.is_finite():
        raise ValueError(f"Gold item {item_id}: expected_value must be finite")
    return parsed


def _parse_page(value: Any, item_id: str, field: str) -> int | None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 1
    ):
        raise ValueError(f"Gold item {item_id}: {field} must be null or a positive integer")
    return value


def _parse_sources(
    raw: dict[str, Any], item_id: str, evidence_requirement: str
) -> tuple[_GoldSource, ...]:
    if evidence_requirement == "single":
        source_doc_id = _optional_string(raw, "source_doc_id", item_id)
        if source_doc_id is None:
            return ()
        if not source_doc_id.startswith("DOC-"):
            raise ValueError(f"Gold item {item_id}: source_doc_id must use the DOC- prefix")
        return (
            _GoldSource(
                doc_id=source_doc_id,
                page=_parse_page(raw.get("source_page"), item_id, "source_page"),
                publisher=None,
                content_hash=None,
            ),
        )

    raw_sources = raw.get("independent_sources")
    if not isinstance(raw_sources, list) or len(raw_sources) < 2:
        raise ValueError(
            f"Gold item {item_id}: multiple evidence requires at least two "
            "reviewed independent_sources"
        )
    sources: list[_GoldSource] = []
    seen_doc_ids: set[str] = set()
    for index, source in enumerate(raw_sources):
        if not isinstance(source, dict):
            raise ValueError(
                f"Gold item {item_id}: independent_sources[{index}] must be an object"
            )
        doc_id = _required_string(source, "doc_id", item_id)
        if not doc_id.startswith("DOC-"):
            raise ValueError(
                f"Gold item {item_id}: independent source doc_id must use the DOC- prefix"
            )
        if doc_id in seen_doc_ids:
            raise ValueError(f"Gold item {item_id}: independent source doc_id must be unique")
        seen_doc_ids.add(doc_id)
        sources.append(
            _GoldSource(
                doc_id=doc_id,
                page=_parse_page(source.get("page"), item_id, "independent source page"),
                publisher=_required_string(source, "publisher", item_id),
                content_hash=_required_string(source, "content_hash", item_id),
            )
        )
    if len({source.publisher for source in sources}) < 2 or len(
        {source.content_hash for source in sources}
    ) < 2:
        raise ValueError(
            f"Gold item {item_id}: multiple evidence requires different publishers "
            "and content_hash values"
        )
    return tuple(sources)


def _load_gold(gold_path: str) -> list[_GoldItem]:
    path = Path(gold_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Gold Standard file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gold Standard file is not valid JSON: {path} (line {exc.lineno})"
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Gold Standard root must be an object containing an items list")

    items: list[_GoldItem] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(payload["items"]):
        if not isinstance(raw, dict):
            raise ValueError(f"Gold item at index {index} must be an object")
        item_id = _required_string(raw, "item_id", f"at index {index}")
        if item_id in seen_ids:
            raise ValueError(f"Gold item_id must be unique: {item_id}")
        seen_ids.add(item_id)

        required = raw.get("required")
        if not isinstance(required, bool):
            raise ValueError(f"Gold item {item_id}: required must be a boolean")

        evidence_requirement = _required_string(raw, "evidence_requirement", item_id)
        if evidence_requirement not in {"single", "multiple"}:
            raise ValueError(
                f"Gold item {item_id}: evidence_requirement must be single or multiple"
            )

        items.append(
            _GoldItem(
                item_id=item_id,
                item_type=_required_string(raw, "item_type", item_id),
                expected_text=_required_string(raw, "expected_text", item_id),
                expected_value=_parse_expected_value(raw, item_id),
                unit=_optional_string(raw, "unit", item_id),
                required=required,
                sources=_parse_sources(raw, item_id, evidence_requirement),
                industry_metric_id=_optional_string(raw, "industry_metric_id", item_id),
                evidence_requirement=evidence_requirement,
            )
        )
    return items


def _report_claims(report: ResearchReport) -> list[Claim]:
    """Return non-rejected substantive claims, excluding unresolved placeholders."""

    return [
        claim
        for claim in [*report.claims, *report.risks]
        if claim.status != "reject" and claim.claim_type != "unresolved"
    ]


def _formal_claims(report: ResearchReport) -> list[Claim]:
    """Return claims eligible for the formal body under CONTRACTS.md."""

    return [claim for claim in [*report.claims, *report.risks] if claim.status == "pass"]


def _claim_matches_item(claim: Claim, item: _GoldItem) -> bool:
    metric_matches = (
        item.industry_metric_id is None
        or item.industry_metric_id in claim.industry_metric_ids
    )
    text_matches = item.expected_text.casefold() in claim.text.casefold()
    return metric_matches and text_matches


def _claim_has_expected_value(claim: Claim, item: _GoldItem) -> bool:
    if item.expected_value is None:
        return True
    if item.unit is not None and item.unit.casefold() not in claim.text.casefold():
        return False
    for token in _NUMBER_PATTERN.findall(claim.text):
        try:
            if Decimal(token.replace(",", "")) == item.expected_value:
                return True
        except InvalidOperation:
            continue
    return False


def _location_matches(evidence: Evidence, item: _GoldItem) -> bool:
    return any(
        evidence.doc_id == source.doc_id
        and (source.page is None or evidence.page == source.page)
        for source in item.sources
    )


def _evidence_matches_report(evidence: Evidence, report: ResearchReport) -> bool:
    company_matches = evidence.company_name in {None, report.company_name}
    industry_matches = evidence.industry_id in {None, report.industry_id}
    return company_matches and industry_matches


def _evidence_requirement_met(
    claim: Claim,
    item: _GoldItem,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    cited_doc_ids = {
        evidence.doc_id
        for evidence_id in claim.evidence_ids
        if (evidence := evidence_by_id.get(evidence_id)) is not None
    }
    cited_sources = [source for source in item.sources if source.doc_id in cited_doc_ids]
    if item.evidence_requirement == "single":
        return bool(cited_sources)
    return (
        len(cited_sources) >= 2
        and len({source.publisher for source in cited_sources}) >= 2
        and len({source.content_hash for source in cited_sources}) >= 2
    )


def evaluate_report(report: ResearchReport, gold_path: str) -> dict[str, float]:
    """Calculate deterministic D-001 metrics for one structured report.

    Rate metrics are returned on a 0..1 scale.  When a denominator is empty,
    the corresponding rate is defined as ``0.0``.  ``cutoff_violation_count``
    is a count represented as float to preserve the public return type.
    """

    gold_items = _load_gold(gold_path)
    substantive_claims = _report_claims(report)
    formal_claims = _formal_claims(report)
    evidence_by_id = {evidence.evidence_id: evidence for evidence in report.evidence_index}

    required_items = [item for item in gold_items if item.required]
    covered_required_items = 0
    for item in required_items:
        if any(
            _claim_matches_item(claim, item) and _claim_has_expected_value(claim, item)
            for claim in substantive_claims
        ):
            covered_required_items += 1

    numeric_items = [item for item in gold_items if item.expected_value is not None]
    checked_numeric_items = 0
    numeric_errors = 0
    for item in numeric_items:
        candidates = [claim for claim in substantive_claims if _claim_matches_item(claim, item)]
        if not candidates:
            continue
        checked_numeric_items += 1
        if not any(_claim_has_expected_value(claim, item) for claim in candidates):
            numeric_errors += 1

    required_metric_ids = {
        item.industry_metric_id
        for item in required_items
        if item.industry_metric_id is not None
    }
    checked_metric_ids = {
        metric_id
        for claim in [*report.claims, *report.risks, *report.unresolved_items]
        if claim.status != "reject"
        for metric_id in claim.industry_metric_ids
    }

    checked_references = 0
    valid_references = 0
    accurate_locations = 0
    cutoff_violations: set[str] = set()
    for claim in formal_claims:
        matching_items = [
            item
            for item in gold_items
            if _claim_matches_item(claim, item) and _claim_has_expected_value(claim, item)
        ]
        adequately_supported_items = [
            item
            for item in matching_items
            if _evidence_requirement_met(claim, item, evidence_by_id)
        ]
        for evidence_id in claim.evidence_ids:
            checked_references += 1
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                continue
            if evidence.published_at > report.cutoff_date:
                cutoff_violations.add(evidence.evidence_id)

            location_accurate = any(
                _location_matches(evidence, item) for item in matching_items
            )
            if location_accurate:
                accurate_locations += 1
            if (
                location_accurate
                and any(
                    _location_matches(evidence, item)
                    for item in adequately_supported_items
                )
                and evidence.review_status == "verified"
                and evidence.published_at <= report.cutoff_date
                and _evidence_matches_report(evidence, report)
            ):
                valid_references += 1

    return {
        "key_factor_coverage_rate": _rate(
            covered_required_items, len(required_items)
        ),
        "evidence_validity_rate": _rate(valid_references, checked_references),
        "citation_location_accuracy_rate": _rate(
            accurate_locations, checked_references
        ),
        "numeric_error_rate": _rate(numeric_errors, checked_numeric_items),
        "cutoff_violation_count": float(len(cutoff_violations)),
        "industry_metric_coverage_rate": _rate(
            len(required_metric_ids & checked_metric_ids), len(required_metric_ids)
        ),
    }
