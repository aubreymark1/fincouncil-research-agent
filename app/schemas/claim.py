"""Research claim schema."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Claim(BaseModel):
    """A typed conclusion whose support is tracked by evidence IDs."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, pattern=r"^CL-[A-Za-z0-9][A-Za-z0-9._-]*$")
    text: str = Field(min_length=1)
    claim_type: Literal["fact", "change", "analysis", "risk", "unresolved"]
    evidence_ids: list[str]
    calculation: str | None = Field(default=None, min_length=1)
    confidence: float = Field(ge=0, le=1)
    industry_metric_ids: list[str]
    status: Literal["draft", "pass", "review", "reject"]

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        for evidence_id in values:
            if not evidence_id.startswith("EV-"):
                raise ValueError("evidence_ids must contain stable EV- identifiers")
        return values

    @model_validator(mode="after")
    def validate_support(self) -> Self:
        if self.claim_type != "unresolved" and not self.evidence_ids:
            raise ValueError("fact, change, analysis, and risk claims require evidence_ids")
        if self.claim_type == "unresolved" and self.status == "pass":
            raise ValueError("unresolved claims cannot have status=pass")
        return self
