"""Public, redacted activity events emitted during a research run."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_PUBLIC_DETAIL_KEYS = frozenset({
    "query",
    "count",
    "first_title",
    "document_count",
    "evidence_count",
    "excluded_count",
    "provider",
    "model",
    "reason",
})


class RunEvent(BaseModel):
    """A user-safe observation of one pipeline or tool activity."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=r"^EVT-[A-Za-z0-9][A-Za-z0-9._-]*$")
    run_id: str = Field(pattern=r"^RUN-[A-Za-z0-9][A-Za-z0-9._-]*$")
    sequence: int = Field(ge=1)
    occurred_at: datetime
    kind: Literal["stage", "tool_start", "tool_result", "warning", "error"]
    tool_name: str | None = None
    tool_call_id: str | None = Field(default=None, pattern=r"^CALL-[A-Za-z0-9][A-Za-z0-9._-]*$")
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    status: Literal["running", "success", "warning", "failed"] = "running"
    duration_ms: int | None = Field(default=None, ge=0)
    source_ids: list[str] = Field(default_factory=list)
    public_details: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("public_details")
    @classmethod
    def validate_public_details(cls, value: dict[str, str | int | float | bool]):
        unknown = set(value) - ALLOWED_PUBLIC_DETAIL_KEYS
        if unknown:
            raise ValueError(f"public detail key not allowed: {', '.join(sorted(unknown))}")
        return value
