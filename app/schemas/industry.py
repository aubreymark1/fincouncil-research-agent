"""Industry configuration schemas."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetricRule(BaseModel):
    """One industry-specific metric requirement."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    keywords: list[str]
    evidence_types: list[str] = Field(min_length=1)
    required: bool
    evidence_requirement: Literal["single", "multiple"]
    missing_action: Literal["warn", "review", "reject"]


class RiskRule(BaseModel):
    """One industry-specific risk trigger."""

    model_config = ConfigDict(extra="forbid")

    risk_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    trigger_description: str = Field(min_length=1)
    metric_ids: list[str] = Field(min_length=1)
    required_evidence_types: list[str]
    severity: Literal["low", "medium", "high"]


class IndustryConfig(BaseModel):
    """Configuration consumed by industry checks and report sections."""

    model_config = ConfigDict(extra="forbid")

    industry_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    required_metrics: list[MetricRule] = Field(min_length=1)
    event_taxonomy: list[str]
    risk_rules: list[RiskRule]
    report_sections: list[str] = Field(min_length=1)
    retrieval_keywords: list[str]

    @model_validator(mode="after")
    def validate_ids_and_risk_metric_references(self) -> Self:
        metric_ids = [metric.metric_id for metric in self.required_metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("metric_id must be unique within one industry configuration")

        risk_ids = [rule.risk_id for rule in self.risk_rules]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError("risk_id must be unique within one industry configuration")

        known_metric_ids = set(metric_ids)
        for rule in self.risk_rules:
            unknown = sorted(set(rule.metric_ids) - known_metric_ids)
            if unknown:
                raise ValueError(
                    f"risk rule {rule.risk_id} references unknown metric_ids: {unknown}"
                )
        return self
