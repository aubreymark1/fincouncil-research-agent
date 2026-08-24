"""Input schema for a research run."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResearchRequest(BaseModel):
    """User-provided parameters for one reproducible research run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, pattern=r"^RUN-[A-Za-z0-9][A-Za-z0-9._-]*$")
    company_name: str = Field(min_length=1)
    ticker: str | None = Field(default=None, min_length=1)
    industry_id: str = Field(min_length=1)
    cutoff_date: date
    comparison_start: date | None = None
    comparison_end: date | None = None
    source_manifest_path: str = Field(min_length=1)
    output_dir: str = Field(min_length=1)

    @field_validator("source_manifest_path")
    @classmethod
    def validate_manifest_path(cls, value: str) -> str:
        """Require a path value; filesystem existence is checked by ingestion."""

        if not Path(value).parts:
            raise ValueError("source_manifest_path must be a non-empty path")
        return value

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str) -> str:
        """Keep report output below an outputs directory.

        Relative paths must start with ``outputs``. Absolute paths are accepted
        when one of their path components is ``outputs``; the project root is
        intentionally resolved by the CLI rather than embedded in this model.
        """

        path = Path(value)
        parts = tuple(part.lower() for part in path.parts)
        if not parts or "outputs" not in parts:
            raise ValueError("output_dir must be located under the project outputs directory")
        if not path.is_absolute() and parts[0] != "outputs":
            raise ValueError("relative output_dir must start with outputs/")
        return value

    @model_validator(mode="after")
    def validate_comparison_range(self) -> Self:
        if (
            self.comparison_start is not None
            and self.comparison_end is not None
            and self.comparison_start > self.comparison_end
        ):
            raise ValueError("comparison_start must not be later than comparison_end")
        return self
