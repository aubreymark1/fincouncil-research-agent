"""Gold Standard schema and validation for deterministic evaluation (D-001).

A Gold Standard is the human-reviewed source of truth used by
:mod:`evaluation.metrics`.  This module owns the file format and the
validation rules so D-001 can be tested independently of metric scoring:

- the root ``required_metric_ids`` must exactly match the ``required: true``
  metric IDs declared by the industry configuration;
- every ``industry_metric_id`` on an item must exist in that configuration;
- single-source items use ``source_doc_id``/``source_page``;
- multiple-source items require at least two independent sources with
  distinct normalized publishers and content hashes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.industry.loader import IndustryConfigError, load_industry_config


@dataclass(frozen=True)
class GoldSource:
    """One source location referenced by a Gold item."""

    doc_id: str
    page: int | None
    publisher: str | None
    content_hash: str | None


@dataclass(frozen=True)
class GoldItem:
    """One expected fact or required item in the Gold Standard."""

    item_id: str
    item_type: str
    expected_text: str
    expected_value: Decimal | None
    unit: str | None
    required: bool
    sources: tuple[GoldSource, ...]
    industry_metric_id: str | None
    evidence_requirement: str


@dataclass(frozen=True)
class GoldStandard:
    """A validated Gold Standard document."""

    items: tuple[GoldItem, ...]
    required_metric_ids: frozenset[str]
    required_metric_ids_source: str


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


def normalize_identity(value: str | None) -> str | None:
    """Normalize a publisher or content hash for independence comparisons."""
    return value.strip().casefold() if value is not None else None


def _parse_page(value: Any, item_id: str, field: str) -> int | None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 1
    ):
        raise ValueError(f"Gold item {item_id}: {field} must be null or a positive integer")
    return value


def _parse_sources(
    raw: dict[str, Any], item_id: str, evidence_requirement: str
) -> tuple[GoldSource, ...]:
    if evidence_requirement == "single":
        source_doc_id = _optional_string(raw, "source_doc_id", item_id)
        if source_doc_id is None:
            return ()
        if not source_doc_id.startswith("DOC-"):
            raise ValueError(f"Gold item {item_id}: source_doc_id must use the DOC- prefix")
        return (
            GoldSource(
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
    sources: list[GoldSource] = []
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
            GoldSource(
                doc_id=doc_id,
                page=_parse_page(source.get("page"), item_id, "independent source page"),
                publisher=_required_string(source, "publisher", item_id),
                content_hash=_required_string(source, "content_hash", item_id),
            )
        )
    if len({normalize_identity(source.publisher) for source in sources}) < 2 or len(
        {normalize_identity(source.content_hash) for source in sources}
    ) < 2:
        raise ValueError(
            f"Gold item {item_id}: multiple evidence requires different publishers "
            "and content_hash values"
        )
    return tuple(sources)


def load_gold_standard(gold_path: str, industry_id: str) -> GoldStandard:
    """Load and validate a Gold Standard file for an industry.

    Parameters
    ----------
    gold_path:
        Path to the Gold Standard JSON document.
    industry_id:
        Industry whose configuration provides the authoritative metric IDs.

    Returns
    -------
    GoldStandard
        A validated, immutable Gold Standard.

    Raises
    ------
    ValueError
        When the file is missing, malformed, or violates the D-001 schema.
    """
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

    raw_required_metric_ids = payload.get("required_metric_ids")
    if not isinstance(raw_required_metric_ids, list) or not raw_required_metric_ids:
        raise ValueError(
            "Gold Standard root must contain the complete non-empty required_metric_ids list"
        )
    required_metric_ids: list[str] = []
    for index, metric_id in enumerate(raw_required_metric_ids):
        if not isinstance(metric_id, str) or not metric_id.strip():
            raise ValueError(
                f"Gold required_metric_ids[{index}] must be a non-empty string"
            )
        required_metric_ids.append(metric_id.strip())
    if len(set(required_metric_ids)) != len(required_metric_ids):
        raise ValueError("Gold required_metric_ids must be unique")
    required_metric_ids_source = _required_string(
        payload, "required_metric_ids_source", "root"
    )

    try:
        config = load_industry_config(industry_id)
    except IndustryConfigError as exc:
        raise ValueError(
            f"Gold Standard cannot load industry config for {industry_id!r}: {exc}"
        ) from exc
    known_metric_ids = {metric.metric_id for metric in config.required_metrics}
    config_required_metric_ids = {
        metric.metric_id for metric in config.required_metrics if metric.required
    }
    gold_required_metric_ids = set(required_metric_ids)
    missing_required_metric_ids = sorted(config_required_metric_ids - gold_required_metric_ids)
    extra_required_metric_ids = sorted(gold_required_metric_ids - config_required_metric_ids)
    if missing_required_metric_ids or extra_required_metric_ids:
        raise ValueError(
            "Gold required_metric_ids must exactly match the industry config's "
            "required=true metrics; "
            f"missing={missing_required_metric_ids}, extra={extra_required_metric_ids}"
        )

    items: list[GoldItem] = []
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

        expected_value = _parse_expected_value(raw, item_id)
        unit = _optional_string(raw, "unit", item_id)
        if expected_value is not None and unit is None:
            raise ValueError(
                f"Gold item {item_id}: unit is required when expected_value is numeric"
            )
        industry_metric_id = _optional_string(raw, "industry_metric_id", item_id)
        if industry_metric_id is not None and industry_metric_id not in known_metric_ids:
            raise ValueError(
                f"Gold item {item_id}: unknown industry_metric_id {industry_metric_id!r}"
            )
        item = GoldItem(
            item_id=item_id,
            item_type=_required_string(raw, "item_type", item_id),
            expected_text=_required_string(raw, "expected_text", item_id),
            expected_value=expected_value,
            unit=unit,
            required=required,
            sources=_parse_sources(raw, item_id, evidence_requirement),
            industry_metric_id=industry_metric_id,
            evidence_requirement=evidence_requirement,
        )
        items.append(item)
    return GoldStandard(
        items=tuple(items),
        required_metric_ids=frozenset(required_metric_ids),
        required_metric_ids_source=required_metric_ids_source,
    )
