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


def _config_required_metric_ids(industry_id: str) -> set[str]:
    config = load_industry_config(industry_id)
    return {metric.metric_id for metric in config.required_metrics if metric.required}


def test_food_gold_template_matches_food_config_required_metrics() -> None:
    gold = load_gold_standard(str(FOOD_GOLD), "food_beverage")

    assert gold.required_metric_ids == frozenset(
        _config_required_metric_ids("food_beverage")
    )
    assert gold.items == ()


def test_bank_gold_template_matches_bank_config_required_metrics() -> None:
    gold = load_gold_standard(str(BANK_GOLD), "banking")

    assert gold.required_metric_ids == frozenset(
        _config_required_metric_ids("banking")
    )
    assert gold.items == ()


def test_unknown_item_metric_id_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(FOOD_GOLD.read_text(encoding="utf-8"))
    payload["items"] = [
        {
            "item_id": "GOLD-UNKNOWN",
            "item_type": "key_factor",
            "expected_text": "测试文本",
            "expected_value": None,
            "unit": None,
            "required": True,
            "source_doc_id": "DOC-001",
            "source_page": 1,
            "industry_metric_id": "not_a_metric",
            "evidence_requirement": "single",
        }
    ]
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown industry_metric_id"):
        load_gold_standard(str(path), "food_beverage")


def test_missing_required_metric_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(FOOD_GOLD.read_text(encoding="utf-8"))
    payload["required_metric_ids"].remove("food_safety")
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="must exactly match"):
        load_gold_standard(str(path), "food_beverage")


def test_duplicate_item_id_is_rejected(tmp_path: Path) -> None:
    item = {
        "item_id": "GOLD-DUP",
        "item_type": "key_factor",
        "expected_text": "重复",
        "expected_value": None,
        "unit": None,
        "required": True,
        "source_doc_id": "DOC-001",
        "source_page": 1,
        "industry_metric_id": "revenue_growth",
        "evidence_requirement": "single",
    }
    payload = json.loads(FOOD_GOLD.read_text(encoding="utf-8"))
    payload["items"] = [item, item]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="item_id must be unique"):
        load_gold_standard(str(path), "food_beverage")


def test_multiple_sources_require_distinct_normalized_publishers(
    tmp_path: Path,
) -> None:
    payload = json.loads(FOOD_GOLD.read_text(encoding="utf-8"))
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
