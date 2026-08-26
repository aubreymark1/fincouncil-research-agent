"""Deterministic tests for D-001 report evaluation metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas import ResearchReport
from evaluation.metrics import evaluate_report


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "evaluation"


def _load_report(name: str = "report_sample.json") -> ResearchReport:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return ResearchReport.model_validate(payload)


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
            "industry_metric_coverage_rate": 1.0,
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
        "industry_metric_id": "revenue",
        "evidence_requirement": "single",
    }
    gold_path = tmp_path / "duplicate.json"
    gold_path.write_text(
        json.dumps({"items": [item, item]}, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="item_id must be unique"):
        evaluate_report(_load_report(), str(gold_path))


def test_multiple_evidence_requirement_needs_two_documents(tmp_path: Path) -> None:
    gold_path = tmp_path / "multiple.json"
    gold_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "item_id": "GOLD-MULTIPLE",
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
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    metrics = evaluate_report(_load_report(), str(gold_path))

    assert metrics["citation_location_accuracy_rate"] == 1 / 3
    assert metrics["evidence_validity_rate"] == 0.0


def test_missing_gold_file_has_actionable_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="Gold Standard file does not exist"):
        evaluate_report(_load_report(), str(missing))
