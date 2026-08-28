"""Deterministic report metrics backed by a reviewed Gold Standard file.

The evaluator deliberately performs no model calls and no fuzzy semantic
matching.  A Gold item is matched to a report claim by ``industry_metric_id``
and an exact (case-insensitive) ``expected_text`` substring.  This keeps test
and experiment runs reproducible and makes the human-reviewed Gold file the
source of truth.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.schemas import Claim, Evidence, ResearchReport
from evaluation.gold import GoldItem, load_gold_standard, normalize_identity


_NUMBER_TOKEN = r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?"
_NUMBER_PATTERN = re.compile(_NUMBER_TOKEN)


def _rate(numerator: int, denominator: int) -> float:
    """Return a stable 0..1 rate; an empty population is defined as 0.0."""

    return numerator / denominator if denominator else 0.0


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


def _claim_matches_item(claim: Claim, item: GoldItem) -> bool:
    metric_matches = (
        item.industry_metric_id is None
        or item.industry_metric_id in claim.industry_metric_ids
    )
    text_matches = item.expected_text.casefold() in claim.text.casefold()
    return metric_matches and text_matches


def _number_occurrences(text: str, unit: str | None) -> list[tuple[int, int, Decimal]]:
    pattern = _NUMBER_PATTERN
    if unit is not None:
        pattern = re.compile(f"({_NUMBER_TOKEN})\\s*{re.escape(unit)}", re.IGNORECASE)
    occurrences: list[tuple[int, int, Decimal]] = []
    for match in pattern.finditer(text):
        token = match.group(1) if unit is not None else match.group(0)
        try:
            occurrences.append(
                (match.start(), match.end(), Decimal(token.replace(",", "")))
            )
        except InvalidOperation:
            continue
    return occurrences


def _text_has_expected_value(text: str, item: GoldItem) -> bool:
    if item.expected_value is None:
        return True
    return any(
        value == item.expected_value
        for _, _, value in _number_occurrences(text, item.unit)
    )


def _text_supports_item(text: str, item: GoldItem) -> bool:
    return (
        item.expected_text.casefold() in text.casefold()
        and _text_has_expected_value(text, item)
    )


def _claim_has_expected_value(claim: Claim, item: GoldItem) -> bool:
    return _text_has_expected_value(claim.text, item)


def _evidence_supports_item(evidence: Evidence, item: GoldItem) -> bool:
    return _text_supports_item(evidence.quote, item) and _text_supports_item(
        evidence.fact_text, item
    )


def _location_matches(evidence: Evidence, item: GoldItem) -> bool:
    return any(
        evidence.doc_id == source.doc_id
        and (source.page is None or evidence.page == source.page)
        for source in item.sources
    )


def _evidence_matches_report(evidence: Evidence, report: ResearchReport) -> bool:
    company_matches = evidence.company_name in {None, report.company_name}
    industry_matches = evidence.industry_id in {None, report.industry_id}
    return company_matches and industry_matches


def _evidence_is_eligible(evidence: Evidence, report: ResearchReport) -> bool:
    return (
        evidence.review_status == "verified"
        and evidence.published_at <= report.cutoff_date
        and _evidence_matches_report(evidence, report)
    )


def _evidence_requirement_met(
    claim: Claim,
    item: GoldItem,
    evidence_by_id: dict[str, Evidence],
    report: ResearchReport,
) -> bool:
    supporting_doc_ids = {
        evidence.doc_id
        for evidence_id in claim.evidence_ids
        if (evidence := evidence_by_id.get(evidence_id)) is not None
        and _evidence_is_eligible(evidence, report)
        and _location_matches(evidence, item)
        and _evidence_supports_item(evidence, item)
    }
    cited_sources = [
        source for source in item.sources if source.doc_id in supporting_doc_ids
    ]
    if item.evidence_requirement == "single":
        return bool(cited_sources)
    return (
        len(cited_sources) >= 2
        and len({normalize_identity(source.publisher) for source in cited_sources}) >= 2
        and len({normalize_identity(source.content_hash) for source in cited_sources}) >= 2
    )


def _numeric_error_counts(
    claims: list[Claim], items: tuple[GoldItem, ...]
) -> tuple[int, int]:
    checked: dict[tuple[str, int, int, str], tuple[Decimal, set[Decimal]]] = {}
    numeric_items = [item for item in items if item.expected_value is not None]
    for claim in claims:
        for item in numeric_items:
            if not _claim_matches_item(claim, item):
                continue
            assert item.expected_value is not None
            assert item.unit is not None
            normalized_unit = item.unit.strip().casefold()
            for start, end, value in _number_occurrences(claim.text, item.unit):
                key = (claim.claim_id, start, end, normalized_unit)
                if key not in checked:
                    checked[key] = (value, set())
                checked[key][1].add(item.expected_value)
    errors = sum(value not in expected for value, expected in checked.values())
    return errors, len(checked)


def evaluate_report(report: ResearchReport, gold_path: str) -> dict[str, float]:
    """Calculate deterministic D-001 metrics for one structured report.

    Rate metrics are returned on a 0..1 scale. Numeric errors count individual
    unit-qualified numbers in matching report claims. Industry coverage uses
    the complete ``required_metric_ids`` frozen at the Gold root. Evidence is
    valid only when both its verbatim quote and normalized fact support the
    Gold text/value/unit. When a denominator is empty, its rate is ``0.0``.
    ``cutoff_violation_count`` is a float to preserve the public return type.
    """

    gold = load_gold_standard(gold_path, report.industry_id)
    gold_items = gold.items
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

    numeric_errors, checked_numbers = _numeric_error_counts(
        substantive_claims, gold_items
    )

    required_metric_ids = gold.required_metric_ids
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
            if _evidence_requirement_met(claim, item, evidence_by_id, report)
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
                    and _evidence_supports_item(evidence, item)
                    for item in adequately_supported_items
                )
                and _evidence_is_eligible(evidence, report)
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
        "numeric_error_rate": _rate(numeric_errors, checked_numbers),
        "cutoff_violation_count": float(len(cutoff_violations)),
        "industry_metric_coverage_rate": _rate(
            len(required_metric_ids & checked_metric_ids), len(required_metric_ids)
        ),
    }
