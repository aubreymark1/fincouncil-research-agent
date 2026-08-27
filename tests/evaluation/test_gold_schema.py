"""Tests for the D-001 Gold Standard schema and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.industry.loader import load_industry_config
from evaluation.gold import load_gold_standard


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "evaluation"
FOOD_GOLD = FIXTURES / "food_gold.json"
BANK_GOLD = FIXTURES / "bank_gold.json"
SIGNED_FOOD_GOLD = FIXTURES / "metrics_gold_sample.json"


def _config_required_metric_ids(industry_id: str) -> set[str]:
    config = load_industry_config(industry_id)
    return {metric.metric_id for metric in config.required_metrics if metric.required}


def _load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_food_gold_template_pending_signoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="not signed"):
        load_gold_standard(str(FOOD_GOLD), "food_beverage")


def test_bank_gold_template_pending_signoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="not signed"):
        load_gold_standard(str(BANK_GOLD), "banking")


def test_signed_food_gold_matches_food_config_required_metrics() -> None:
    gold = load_gold_standard(str(SIGNED_FOOD_GOLD), "food_beverage")

    assert gold.required_metric_ids == frozenset(
        _config_required_metric_ids("food_beverage")
    )
    assert len(gold.items) > 0


def test_signed_bank_gold_matches_bank_config_required_metrics(tmp_path: Path) -> None:
    payload = _load_payload(BANK_GOLD)
    payload["status"] = "signed"
    payload["items"] = [
        {
            "item_id": "GOLD-BANK-001",
            "item_type": "key_factor",
            "expected_text": "净息差",
            "expected_value": 1.8,
            "unit": "%",
            "required": True,
            "source_doc_id": "DOC-BANK-001",
            "source_page": 10,
            "industry_metric_id": "net_interest_margin",
            "evidence_requirement": "single",
        }
    ]
    path = tmp_path / "bank_signed.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    gold = load_gold_standard(str(path), "banking")

    assert gold.required_metric_ids == frozenset(
        _config_required_metric_ids("banking")
    )


def test_empty_items_gold_is_rejected_even_when_signed(tmp_path: Path) -> None:
    payload = _load_payload(FOOD_GOLD)
    payload["status"] = "signed"
    path = tmp_path / "empty_signed.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="at least one item"):
        load_gold_standard(str(path), "food_beverage")


def test_unknown_item_metric_id_is_rejected(tmp_path: Path) -> None:
    payload = _load_payload(SIGNED_FOOD_GOLD)
    payload["items"][2]["industry_metric_id"] = "not_a_metric"
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown industry_metric_id"):
        load_gold_standard(str(path), "food_beverage")


def test_missing_required_metric_is_rejected(tmp_path: Path) -> None:
    payload = _load_payload(SIGNED_FOOD_GOLD)
    payload["required_metric_ids"].remove("food_safety")
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="must exactly match"):
        load_gold_standard(str(path), "food_beverage")


def test_duplicate_item_id_is_rejected(tmp_path: Path) -> None:
    payload = _load_payload(SIGNED_FOOD_GOLD)
    item = payload["items"][0]
    payload["items"] = [item, item]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="item_id must be unique"):
        load_gold_standard(str(path), "food_beverage")


def test_multiple_sources_require_distinct_normalized_publishers(
    tmp_path: Path,
) -> None:
    payload = _load_payload(SIGNED_FOOD_GOLD)
    payload["items"] = [
        {
            "item_id": "GOLD-MULTI",
            "item_type": "key_factor",
            "expected_text": "食品安全",
            "expected_value": None,
            "unit": None,
            "required": True,
            "source_doc_id": None,
            "source_page": None,
            "industry_metric_id": "food_safety",
            "evidence_requirement": "multiple",
            "independent_sources": [
                {
                    "doc_id": "DOC-001",
                    "page": 1,
                    "publisher": "发布方A",
                    "content_hash": "hash-a",
                },
                {
                    "doc_id": "DOC-002",
                    "page": 2,
                    "publisher": " 发布方a ",
                    "content_hash": "hash-b",
                },
            ],
        }
    ]
    path = tmp_path / "publisher.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="different publishers"):
        load_gold_standard(str(path), "food_beverage")


def test_missing_gold_file_has_actionable_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="Gold Standard file does not exist"):
        load_gold_standard(str(missing), "food_beverage")
