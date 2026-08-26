"""Tests for C-001 YAML industry configuration loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.industry import IndustryConfigError, load_industry_config
from app.industry import loader as loader_module


ROOT = Path(__file__).parents[2]
CONFIG_DIR = ROOT / "configs"
FIXTURE_DIR = ROOT / "fixtures" / "industry"


def _expected_config(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _write_yaml(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(content.lstrip(), encoding="utf-8")
    return path


def test_load_food_beverage_config_matches_expected() -> None:
    config = load_industry_config("food_beverage")

    assert config.model_dump(mode="json") == _expected_config("food_config_expected.json")
    assert config.industry_id == "food_beverage"
    assert any(metric.metric_id == "inventory" and metric.required for metric in config.required_metrics)
    assert all(metric.metric_id != "net_interest_margin" for metric in config.required_metrics)


def test_load_banking_config_matches_expected() -> None:
    config = load_industry_config("banking")

    assert config.model_dump(mode="json") == _expected_config("bank_config_expected.json")
    assert config.industry_id == "banking"
    assert any(
        metric.metric_id == "net_interest_margin" and metric.required
        for metric in config.required_metrics
    )
    assert all(metric.metric_id != "inventory" for metric in config.required_metrics)


def test_missing_config_file_raises_e200(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E200"


def test_yaml_syntax_error_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_yaml(tmp_path, "food_beverage.yaml", "industry_id: [unclosed\n")
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_non_mapping_yaml_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_yaml(tmp_path, "food_beverage.yaml", "- just\n- a\n- list\n")
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_empty_required_metrics_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics: []
    event_taxonomy: []
    risk_rules: []
    report_sections: [summary]
    retrieval_keywords: []
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_duplicate_metric_id_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: duplicate
        display_name: 指标一
        keywords: [收入]
        required: true
        evidence_requirement: single
        missing_action: warn
      - metric_id: duplicate
        display_name: 指标二
        keywords: [利润]
        required: false
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules: []
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_empty_report_sections_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: [收入]
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules: []
    report_sections: []
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_invalid_missing_action_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: [收入]
        required: true
        evidence_requirement: single
        missing_action: invalid
    event_taxonomy: [业绩]
    risk_rules: []
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_empty_keywords_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: []
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules: []
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_blank_keywords_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: ["   "]
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules: []
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


@pytest.mark.parametrize(
    "bad_id",
    [
        "../secret",
        "a/b",
        "C:\\secret",
        "/etc/passwd",
    ],
)
def test_unsafe_industry_id_raises_e201(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bad_id: str,
) -> None:
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config(bad_id)

    assert exc_info.value.code == "E201"


def test_risk_rule_missing_metric_ids_raises_e201(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: [收入]
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules:
      - risk_id: inventory_pressure
        display_name: 库存压力
        trigger_description: 测试风险规则。
        required_evidence_types: [financial]
        severity: medium
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_risk_rule_unknown_metric_ids_raises_e201(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: [收入]
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules:
      - risk_id: inventory_pressure
        display_name: 库存压力
        trigger_description: 测试风险规则。
        metric_ids: [unknown_metric]
        required_evidence_types: [financial]
        severity: medium
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_duplicate_risk_id_raises_e201(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    content = """
    industry_id: food_beverage
    display_name: 测试
    required_metrics:
      - metric_id: revenue_growth
        display_name: 收入增速
        keywords: [收入]
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules:
      - risk_id: duplicate
        display_name: 风险一
        trigger_description: 测试风险规则一。
        metric_ids: [revenue_growth]
        required_evidence_types: [financial]
        severity: medium
      - risk_id: duplicate
        display_name: 风险二
        trigger_description: 测试风险规则二。
        metric_ids: [revenue_growth]
        required_evidence_types: [financial]
        severity: low
    report_sections: [summary]
    retrieval_keywords: [收入]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_invalid_utf8_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "food_beverage.yaml"
    path.write_bytes(b"industry_id: \xff\xfe\n")
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_read_error_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_yaml(tmp_path, "food_beverage.yaml", "industry_id: food_beverage\n")
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    def raise_oserror(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_text", raise_oserror)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"


def test_industry_id_mismatch_raises_e201(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    content = """
    industry_id: banking
    display_name: 测试
    required_metrics:
      - metric_id: net_interest_margin
        display_name: 净息差
        keywords: [净息差]
        required: true
        evidence_requirement: single
        missing_action: warn
    event_taxonomy: [业绩]
    risk_rules: []
    report_sections: [summary]
    retrieval_keywords: [净息差]
    """
    _write_yaml(tmp_path, "food_beverage.yaml", content)
    monkeypatch.setattr(loader_module, "CONFIG_DIR", tmp_path)

    with pytest.raises(IndustryConfigError) as exc_info:
        load_industry_config("food_beverage")

    assert exc_info.value.code == "E201"
