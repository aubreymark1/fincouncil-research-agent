"""Gold-backed metrics for the narrative-only experiment protocol."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.schemas import Evidence, ResearchReport

from .gold import GoldItem, load_gold_standard


_NUMBER_TOKEN = r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?"
_NUMBER_PATTERN = re.compile(_NUMBER_TOKEN)


def _label_candidates(item: GoldItem) -> list[str]:
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", item.expected_text)
    label = item.expected_text[: match.start() if match else len(item.expected_text)].strip()
    labels = [label]
    for suffix in ("增长", "下降", "上升"):
        if label.endswith(suffix):
            labels.append(label[: -len(suffix)].strip())
    return [value for value in labels if value]


def _contains_expected_value(text: str, item: GoldItem) -> bool:
    if item.expected_value is None:
        return True
    if item.unit is None:
        return any(
            Decimal(token.replace(",", "")) == item.expected_value
            for token in _NUMBER_PATTERN.findall(text)
        )
    pattern = re.compile(
        rf"({_NUMBER_TOKEN})\s*{re.escape(item.unit)}",
        re.IGNORECASE,
    )
    for token in pattern.findall(text):
        try:
            if Decimal(token.replace(",", "")) == item.expected_value:
                return True
        except InvalidOperation:
            continue
    return False


def _text_supports_item(text: str, item: GoldItem) -> bool:
    return (
        any(label.casefold() in text.casefold() for label in _label_candidates(item))
        and _contains_expected_value(text, item)
    )


def _evidence_supports_item(evidence: Evidence, item: GoldItem) -> bool:
    text = f"{evidence.fact_text}\n{evidence.quote}"
    return _text_supports_item(text, item)


def _location_matches(evidence: Evidence, item: GoldItem) -> bool:
    return evidence.doc_id == item.sources[0].doc_id and (
        item.sources[0].page is None or evidence.page == item.sources[0].page
    )


def evaluate_narrative(report: ResearchReport, gold_path: str) -> dict[str, float]:
    """Evaluate narrative text and citations without requiring Claim fields."""

    gold = load_gold_standard(gold_path, report.industry_id)
    required_items = [item for item in gold.items if item.required]
    narrative_text = "\n".join(block.text for block in report.narrative)
    evidence_by_id = {item.evidence_id: item for item in report.evidence_index}
    cited_ids = list(
        dict.fromkeys(
            evidence_id
            for block in report.narrative
            for evidence_id in block.evidence_ids
        )
    )

    covered_items = [
        item for item in required_items if _text_supports_item(narrative_text, item)
    ]
    valid_citations = [
        evidence_id
        for evidence_id in cited_ids
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].review_status == "verified"
        and evidence_by_id[evidence_id].published_at <= report.cutoff_date
        and evidence_by_id[evidence_id].industry_id in {None, report.industry_id}
    ]
    accurate_citations = [
        evidence_id
        for evidence_id in cited_ids
        if evidence_id in evidence_by_id
        and any(
            _location_matches(evidence_by_id[evidence_id], item)
            and _evidence_supports_item(evidence_by_id[evidence_id], item)
            for item in covered_items
        )
    ]
    numeric_items = [item for item in covered_items if item.expected_value is not None]
    numeric_errors = sum(
        not any(
            evidence_id in valid_citations
            and _evidence_supports_item(evidence_by_id[evidence_id], item)
            for evidence_id in cited_ids
        )
        for item in numeric_items
    )
    cutoff_violations = {
        evidence_id
        for evidence_id in cited_ids
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].published_at > report.cutoff_date
    }

    return {
        "key_factor_coverage_rate": (
            len(covered_items) / len(required_items) if required_items else 0.0
        ),
        "evidence_validity_rate": (
            len(valid_citations) / len(cited_ids) if cited_ids else 0.0
        ),
        "citation_location_accuracy_rate": (
            len(accurate_citations) / len(cited_ids) if cited_ids else 0.0
        ),
        "numeric_error_rate": (
            numeric_errors / len(numeric_items) if numeric_items else 0.0
        ),
        "cutoff_violation_count": float(len(cutoff_violations)),
        "industry_metric_coverage_rate": (
            len({item.industry_metric_id for item in covered_items if item.industry_metric_id})
            / len(gold.required_metric_ids)
            if gold.required_metric_ids
            else 0.0
        ),
    }
