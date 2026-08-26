"""Deterministic tests for D-001 report evaluation metrics."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.schemas import ResearchReport
from evaluation.metrics import evaluate_report


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "evaluation"


def _load_report(name: str = "report_sample.json") -> ResearchReport:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return ResearchReport.model_validate(payload)


def _load_gold_payload() -> dict:
    return json.loads(
        (FIXTURES / "metrics_gold_sample.json").read_text(encoding="utf-8")
    )


def _write_multiple_gold(tmp_path: Path) -> Path:
    gold = _load_gold_payload()
    revenue_item = gold["items"][0]
    revenue_item.update(
        {
            "item_id": "GOLD-MULTIPLE",
            "source_doc_id": None,
            "source_page": None,
            "evidence_requirement": "multiple",
            "independent_sources": [
                {
                    "doc_id": "DOC-SYN-001",
                    "page": 42,
                    "publisher": "合成发布方甲",
                    "content_hash": "synthetic-hash-a",
                },
                {
                    "doc_id": "DOC-SYN-005",
                    "page": 7,
                    "publisher": "合成发布方乙",
                    "content_hash": "synthetic-hash-b",
                },
            ],
        }
    )
    gold.update(
        {
            "required_metric_ids_source": "synthetic multiple-source test",
            "required_metric_ids": ["revenue_growth"],
            "items": [revenue_item],
        }
    )
    gold_path = tmp_path / "multiple.json"
    gold_path.write_text(json.dumps(gold, ensure_ascii=False), encoding="utf-8")
    return gold_path


def _report_with_second_revenue_evidence(**updates: object) -> ResearchReport:
    report = _load_report()
    second_update = {
        "evidence_id": "EV-SYN-REV-SECOND",
        "doc_id": "DOC-SYN-005",
        "chunk_id": "CHUNK-SYN-005",
        "page": 7,
    }
    second_update.update(updates)
    second_evidence = report.evidence_index[0].model_copy(update=second_update)
    revenue_claim = report.claims[0].model_copy(
        update={
            "evidence_ids": [
                report.evidence_index[0].evidence_id,
                second_evidence.evidence_id,
            ]
        }
    )
    return report.model_copy(
        update={
            "claims": [revenue_claim, *report.claims[1:]],
            "evidence_index": [*report.evidence_index, second_evidence],
        }
    )


def test_evaluate_report_returns_fixed_expected_metrics() -> None:
    metrics = evaluate_report(
        _load_report(), str(FIXTURES / "metrics_gold_sample.json")
    )

    assert metrics == pytest.approx(
        {
            "key_factor_coverage_rate": 0.5,
            "evidence_validity_rate": 1 / 3,
            "citation_location_accuracy_rate": 2 / 3,
            "numeric_error_rate": 1 / 3,
            "cutoff_violation_count": 1.0,
            "industry_metric_coverage_rate": 2 / 5,
        }
    )


def test_empty_denominators_are_reported_as_zero(tmp_path: Path) -> None:
    report = _load_report().model_copy(
        update={
            "claims": [],
            "risks": [],
            "unresolved_items": [],
            "evidence_index": [],
        }
    )
    gold_path = tmp_path / "optional_gold.json"
    gold_path.write_text(
        json.dumps(
            {
                "required_metric_ids_source": "synthetic empty-denominator test",
                "required_metric_ids": ["food_safety"],
                "items": [
                    {
                        "item_id": "GOLD-OPTIONAL",
                        "item_type": "context",
                        "expected_text": "可选背景",
                        "expected_value": None,
                        "unit": None,
                        "required": False,
                        "source_doc_id": None,
                        "source_page": None,
                        "industry_metric_id": None,
                        "evidence_requirement": "single",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert evaluate_report(report, str(gold_path)) == {
        "key_factor_coverage_rate": 0.0,
        "evidence_validity_rate": 0.0,
        "citation_location_accuracy_rate": 0.0,
        "numeric_error_rate": 0.0,
        "cutoff_violation_count": 0.0,
        "industry_metric_coverage_rate": 0.0,
    }


def test_duplicate_gold_item_id_is_rejected(tmp_path: Path) -> None:
    item = {
        "item_id": "GOLD-DUPLICATE",
        "item_type": "key_factor",
        "expected_text": "收入",
        "expected_value": None,
        "unit": None,
        "required": True,
        "source_doc_id": "DOC-SYN-001",
        "source_page": 1,
        "industry_metric_id": "revenue_growth",
        "evidence_requirement": "single",
    }
    gold_path = tmp_path / "duplicate.json"
    gold_path.write_text(
        json.dumps(
            {
                "required_metric_ids_source": "synthetic duplicate-item test",
                "required_metric_ids": ["revenue_growth"],
                "items": [item, item],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="item_id must be unique"):
        evaluate_report(_load_report(), str(gold_path))


def test_multiple_evidence_requirement_needs_two_documents(tmp_path: Path) -> None:
    gold_path = _write_multiple_gold(tmp_path)

    metrics = evaluate_report(_load_report(), str(gold_path))

    assert metrics["citation_location_accuracy_rate"] == 1 / 3
    assert metrics["evidence_validity_rate"] == 0.0


def test_multiple_two_eligible_sources_are_valid(tmp_path: Path) -> None:
    metrics = evaluate_report(
        _report_with_second_revenue_evidence(), str(_write_multiple_gold(tmp_path))
    )

    assert metrics["evidence_validity_rate"] == pytest.approx(2 / 4)


@pytest.mark.parametrize(
    "invalid_update",
    [
        {"review_status": "pending"},
        {"published_at": date(2026, 8, 21)},
        {"company_name": "其他合成公司"},
        {"industry_id": "banking"},
    ],
    ids=["pending", "post-cutoff", "company-mismatch", "industry-mismatch"],
)
def test_multiple_rejects_individually_ineligible_second_source(
    tmp_path: Path, invalid_update: dict[str, object]
) -> None:
    metrics = evaluate_report(
        _report_with_second_revenue_evidence(**invalid_update),
        str(_write_multiple_gold(tmp_path)),
    )

    assert metrics["evidence_validity_rate"] == 0.0


@pytest.mark.parametrize("field", ["quote", "fact_text"])
def test_same_page_unrelated_evidence_is_not_valid(field: str) -> None:
    report = _load_report()
    unrelated = report.evidence_index[0].model_copy(
        update={field: "渠道库存恢复 12.0%。"}
    )
    report = report.model_copy(
        update={"evidence_index": [unrelated, *report.evidence_index[1:]]}
    )

    metrics = evaluate_report(report, str(FIXTURES / "metrics_gold_sample.json"))

    assert metrics["citation_location_accuracy_rate"] == pytest.approx(2 / 3)
    assert metrics["evidence_validity_rate"] == 0.0


def test_numeric_error_rate_counts_each_reported_number() -> None:
    report = _load_report()
    revenue_claim = report.claims[0].model_copy(
        update={"text": "营业收入同比增长 12.0%，另称实际增长 10.0%。"}
    )
    report = report.model_copy(
        update={"claims": [revenue_claim, *report.claims[1:]]}
    )

    metrics = evaluate_report(report, str(FIXTURES / "metrics_gold_sample.json"))

    assert metrics["numeric_error_rate"] == pytest.approx(2 / 4)


def test_publisher_variants_do_not_create_false_independence(tmp_path: Path) -> None:
    gold_path = tmp_path / "publisher_variants.json"
    gold_path.write_text(
        json.dumps(
            {
                "required_metric_ids_source": "synthetic publisher-normalization test",
                "required_metric_ids": ["revenue_growth"],
                "items": [
                    {
                        "item_id": "GOLD-PUBLISHER-VARIANTS",
                        "item_type": "key_factor",
                        "expected_text": "营业收入同比增长",
                        "expected_value": 12.0,
                        "unit": "%",
                        "required": True,
                        "source_doc_id": None,
                        "source_page": None,
                        "industry_metric_id": "revenue_growth",
                        "evidence_requirement": "multiple",
                        "independent_sources": [
                            {
                                "doc_id": "DOC-SYN-001",
                                "page": 42,
                                "publisher": "公司A",
                                "content_hash": "synthetic-hash-a",
                            },
                            {
                                "doc_id": "DOC-SYN-005",
                                "page": 7,
                                "publisher": " 公司a ",
                                "content_hash": "synthetic-hash-b",
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="different publishers"):
        evaluate_report(_load_report(), str(gold_path))


def test_required_metric_missing_from_gold_items_cannot_score_full(
    tmp_path: Path,
) -> None:
    gold = _load_gold_payload()
    gold["required_metric_ids"].append("raw_material_cost")
    gold_path = tmp_path / "complete_required_metrics.json"
    gold_path.write_text(json.dumps(gold, ensure_ascii=False), encoding="utf-8")

    metrics = evaluate_report(_load_report(), str(gold_path))

    assert metrics["industry_metric_coverage_rate"] == pytest.approx(2 / 6)


def test_unknown_gold_metric_id_is_rejected(tmp_path: Path) -> None:
    gold = _load_gold_payload()
    gold["items"][2]["industry_metric_id"] = "sales_volume"
    gold_path = tmp_path / "unknown_metric.json"
    gold_path.write_text(json.dumps(gold, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown industry_metric_id"):
        evaluate_report(_load_report(), str(gold_path))


def test_channel_metric_id_distinguishes_channel_from_inventory() -> None:
    report = _load_report()
    channel_claim = report.unresolved_items[0].model_copy(
        update={
            "claim_id": "CL-SYN-CHANNEL-PASS",
            "claim_type": "fact",
            "status": "pass",
            "text": "渠道库存下降。",
            "evidence_ids": [],
        }
    )
    channel_report = report.model_copy(
        update={
            "unresolved_items": [],
            "claims": [*report.claims, channel_claim],
        }
    )
    channel_metrics = evaluate_report(
        channel_report, str(FIXTURES / "metrics_gold_sample.json")
    )

    assert channel_metrics["key_factor_coverage_rate"] == pytest.approx(3 / 4)

    inventory_claim = channel_claim.model_copy(
        update={
            "claim_id": "CL-SYN-INVENTORY-PASS",
            "text": "存货余额下降。",
            "industry_metric_ids": ["inventory"],
        }
    )
    inventory_report = report.model_copy(
        update={
            "unresolved_items": [],
            "claims": [*report.claims, inventory_claim],
        }
    )
    inventory_metrics = evaluate_report(
        inventory_report, str(FIXTURES / "metrics_gold_sample.json")
    )

    assert inventory_metrics["key_factor_coverage_rate"] == pytest.approx(2 / 4)


def test_missing_gold_file_has_actionable_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="Gold Standard file does not exist"):
        evaluate_report(_load_report(), str(missing))
