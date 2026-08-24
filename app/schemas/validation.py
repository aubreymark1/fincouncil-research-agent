"""Validation issue schema shared by validators, Critic, and reports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationIssue(BaseModel):
    """A structured problem that must remain visible to downstream modules."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(min_length=1, pattern=r"^ISSUE-[A-Za-z0-9][A-Za-z0-9._-]*$")
    check_name: str = Field(min_length=1)
    severity: Literal["info", "warning", "error", "critical"]
    issue_type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    claim_id: str | None = None
    evidence_id: str | None = None
    report_section: str | None = Field(default=None, min_length=1)
    rerun_required: bool
    human_confirmation_required: bool
    status: Literal["open", "resolved", "accepted_risk"]

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("CL-"):
            raise ValueError("claim_id must use the CL- prefix")
        return value

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("EV-"):
            raise ValueError("evidence_id must use the EV- prefix")
        return value
